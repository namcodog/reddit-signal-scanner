# Phase 0 联调准备度报告（2025-09-20）

> 维护人：Codex 联调小队
> 版本：v0.1
> 目标：把本地 / Staging / 生产三套环境的信息、健康检查、Mock 数据、脱敏方案一次性梳理清楚，作为后续 Phase 1-8 的地基。

---

## 1. 看板速览

| 子任务 | 负责人 | 当前状态 | 交付物 |
| ------ | ------ | -------- | ------ |
| 环境矩阵确认 | Codex | ✅ 完成 | [`integration/environments.yaml`](../../integration/environments.yaml) + 表 2.1 |
| 依赖健康检查脚本 | Codex | ✅ 完成 | [`infrastructure/scripts/env_healthcheck.py`](../../infrastructure/scripts/env_healthcheck.py) |
| Mock 数据准备 | Codex | ✅ 完成 | [`mock_data/phase0/mock_reddit_threads.json`](../../mock_data/phase0/mock_reddit_threads.json) |
| 数据脱敏方案 | Codex | ✅ 完成 | [`infrastructure/scripts/sanitize_snapshot.py`](../../infrastructure/scripts/sanitize_snapshot.py) + 附录 |

> 使用说明：完成 Phase 0 后，请在合并请求中引用此报告版本号，并在联调看板打上 `phase0-done` 标签。

---

## 2. 环境矩阵

### 2.1 三套环境配置一览

| 环境 | API Host | 数据库 | Redis / 消息队列 | 配置文件 | 备注 |
| ---- | -------- | ------ | ---------------- | -------- | ---- |
| Local | `http://localhost:8000` | `postgresql://postgres:postgres@localhost:5432/reddit_signal_scanner` | `redis://localhost:6379/0` (Celery: `/1`, `/2`) | `.env`、`backend/.env` | `make install` + `docker-compose up` 即可拉起 |
| Staging | **待运维提供**（建议 `https://staging.api.reddit-signal.internal`） | 建议 RDS：`postgresql://reddit_stage:***@stage-db:5432/rss` | 托管 Redis / MQ（建议 AWS Elasticache, db=0/1/2） | `.env.staging`（新增，已在 `integration/environments.yaml` 预留） | 需要证书、域名、CI 部署变量同步 |
| Production | **待运维提供**（建议 `https://api.reddit-signal.com`） | 主从 PostgreSQL（连接串见运维密钥库 `prod/rss/postgres`） | 托管 Redis Cluster；Celery 队列同集群 | `.env.production`（新增） | 需要灰度策略：先小流量再全量 |

> 备忘：`integration/environments.yaml` 为单一真源，脚本、文档均引用此文件。Staging / Production 的敏感字段保持 `{{ secret }}` 占位，填充通过密钥管理平台完成。

### 2.2 环境一致性校验

- `make env-check`：保留现有提示，同时建议在 Phase 1 前扩展为：
  1. 校验 Python 3.11.7 版本；
  2. 校验 `backend/venv` 中的关键依赖版本（`httpx`, `redis`, `sqlalchemy`）。
- 当 `integration/environments.yaml` 更新后，需同步跑 `python infrastructure/scripts/env_healthcheck.py --list` 查看是否遗漏。

---

## 3. 依赖健康检查脚本

- 入口：`python infrastructure/scripts/env_healthcheck.py --env local`
- 功能：
  1. 读取 `integration/environments.yaml`；
  2. 对 API 健康检查端点（默认 `/api/health`、`/api/v1/auth/health`）发起请求；
  3. 校验数据库、Redis 连接字符串格式；
  4. 支持 `--output json` 导出巡检结果；
  5. 支持批量巡检 `--env all`。
- 依赖：`httpx`、`pydantic`（项目已内置）。
- 后续计划：集成到 `make env-check`，以及 CI 的 `quick-gate`。

---

## 4. Mock 数据包

- 目录：`mock_data/phase0/`
- 内容：
  - `mock_reddit_threads.json`：标准化的分析任务输入样本，共 3 条，字段包含 `id`、`subreddit`、`author_alias`、`score`、`created_utc`、`content`、`labels`、`metadata`。
  - 所有用户字段已脱敏（`author_alias` 使用哈希、`content` 仅保留公开话题关键字）。
- 导入方式：
  ```bash
  python infrastructure/scripts/sanitize_snapshot.py --input mock_data/phase0/mock_reddit_threads.json \
      --output /tmp/rss_mock_threads_sanitized.json --pretty
  ```
  输出文件可直接用于本地 API `/api/v1/analyze` 联调，或上传到 Redis 队列种子任务。

---

## 5. 数据脱敏方案

- 脚本：`python infrastructure/scripts/sanitize_snapshot.py --input prod_dump.json --output sanitized.json`
- 能力：
  1. 支持 JSON/JSON Lines；
  2. 对 `user`, `author`, `email`, `ip` 等字段做 SHA256 + 前缀保留；
  3. 自动剥离附件、Token 等敏感字段；
  4. 支持样本抽样（`--sample-rate 0.2`）。
- 校验：脚本执行后会输出敏感字段计数，便于审计。
- 后续：可扩展 CSV 支持、字段白名单配置。

---

## 6. 下一步建议

1. 在 CI 中新增 `make env-health` 目标，调用健康检查脚本；
2. 将 `mock_data/phase0` 作为自动化测试的默认种子（结合 Celery 集成测试）；
3. 落实 Staging / Production 的真实连接串，填入 `integration/environments.yaml` 并通过密钥库管理；
4. 在联调看板增设 Phase 0 完成卡片，记录执行人/时间戳。

---

## 附录：命令速查

```bash
# 1. 查看支持的环境
python infrastructure/scripts/env_healthcheck.py --list

# 2. 对所有环境做巡检并导出报告
python infrastructure/scripts/env_healthcheck.py --env all --output report.json

# 3. 对生产快照做脱敏抽样
python infrastructure/scripts/sanitize_snapshot.py --input prod.json --output sanitized.json --sample-rate 0.15

# 4. 使用 Mock 数据写入 Redis 种子队列（示例）
python - <<'PY'
from __future__ import annotations
import json
from pathlib import Path
from redis import Redis

redis_client = Redis.from_url('redis://localhost:6379/0')
data = json.loads(Path('mock_data/phase0/mock_reddit_threads.json').read_text(encoding='utf-8'))
for item in data:
    redis_client.lpush('analysis_queue', json.dumps(item, ensure_ascii=False))
print(f'已写入 {len(data)} 条 mock 任务到 analysis_queue')
PY
```

---

> 如果发现脚本或配置异常，请在 Linear 创建 `INT-PHASE0` 分类任务，并 @Codex 联调小队。
