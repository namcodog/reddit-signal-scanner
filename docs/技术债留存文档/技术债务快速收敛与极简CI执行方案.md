**一句话目标**
- 用“本地快速闸门 + 极简CI自动合并”的方式，在10分钟内给出PR反馈；持续小步合入，2天内把关键技术债收口到可控。

**适用阶段**
- 单人或小团队开发、以“先跑起来、快速收敛”为主的阶段。

**工作模式**
- 本地先跑四项快速闸门，全绿再 push；远端 CI 只做复核并自动合并；重活（集成/覆盖率/性能）改为合并后或定时跑。

**四项快速闸门（本地与CI保持一致）**
- 类型检查：严格通过。命令：`mypy --strict backend/app tests`
- 后端冒烟：仅跑 `smoke` 小集，不依赖真实 DB。命令：`PYTHONPATH=backend:. pytest -p pytest_asyncio -q -m smoke tests/smoke`
- 前端小集：仅组件/Hook/工具单测。命令：`cd frontend && npm ci && npm test -- --run src/__tests__/components src/__tests__/hooks src/__tests__/utils`
- 文件质量检查：结构自检与脏文件守卫。命令：`python infrastructure/scripts/verify_structure.py || true`（本地）

**CI 极简策略**
- 必需检查只保留四项：Type Check / 文件检查 / Backend Quick / Frontend Quick。
- 非必需检查（Integration、后端大集覆盖率、性能基线）改为：合并后（push 到 main）或 `schedule` 定时跑。
- 打开并发抢占：`concurrency` 保持启用，新提交自动取消旧流水。
- 自动合并：开启 `auto-merge (squash)`；单人阶段将 `main` 审批数设为 `0`，后续多人协作再恢复为 `2`。

**后端 Quick Gate 规范**
- Python 版本：3.11
- 依赖：默认使用 `backend/requirements.txt`；若体量过大，单独拆 `backend/requirements_quick.txt`（去掉 `torch/transformers/sentence-transformers` 等重依赖）。
- 关键环境：`PYTHONPATH=backend:.`；如使用 `pytest-asyncio`，显式 `-p pytest_asyncio`。
- 选择用例：`-m smoke tests/smoke`。
- 注意：不要关闭 `PYTEST` 的插件自动加载，或在关闭后显式补齐所需插件，否则会出现 `unrecognized arguments: --asyncio-mode=auto`。

**前端 Quick Gate 规范**
- Node 版本：20；使用 `npm ci` + 仅运行单元小集。
- 缓存：`actions/setup-node` 的 `cache: npm` + `cache-dependency-path: frontend/package-lock.json`。

**文件质量检查 Job 规范**
- 检出+Python 环境+最小依赖（如 `pyyaml`）。
- 两类检查：
  - 危险/可疑文件名（如 `utils.py/test.py/-*` 等）；误提交的 E2E 产物（`frontend/cypress/**`）。
  - 简化结构校验（必要目录存在、冗余扫描可 `|| true`）。
- 输出：结论明确（通过/需清理）+ `GITHUB_STEP_SUMMARY` 里统计表。

**路径感知触发（建议）**
- 后端改动才触发 Backend Quick：
  - `paths: [backend/**, tests/**, .github/workflows/test-quick.yml]`
- 前端改动才触发 Frontend Quick：
  - `paths: [frontend/**, .github/workflows/test-quick.yml]`
- 纯文档改动只跑文件检查：
  - `paths: ["**/*.md", "docs/**"]`

**分支保护与自动合并**
- 单人阶段：`main` 分支审批数设为 `0`，保留四个必需检查；PR 全绿即可自动合并到 `main`。
- 多人阶段：审批数恢复为 `2`；继续保留四个必需检查作为快速闸门。

**仓库卫生（避免无谓红点）**
- 不要把测试/构建产物入库，特别是 `reports/junit.xml`、`htmlcov/`、`.pytest_cache/`。
- 如已被跟踪：在该 PR 中移除改动，并在 `.gitignore` 补充忽略规则（必要时 `git rm --cached`）。

**每日节奏（执行节拍）**
- 每次改动先在本地跑四项快速闸门 → 全绿再 push。
- 每日至少 2 次合入 `main`（哪怕是小步修复），保持滚动收敛。
- 所有重活（Integration/覆盖率/性能）在合并后或定时跑，不阻塞 PR。

**关键指标（持续观测）**
- PR 反馈时间：≤ 10 分钟。
- 必需检查一次通过率：≥ 90%。
- 每日合并频次：≥ 2 次。

**常见卡点与速解**
- 报错 `unrecognized arguments: --asyncio-mode=auto`：
  - 现象：关闭插件自动加载但使用了 `pytest-asyncio` 配置。
  - 解法：不要关闭自动加载，或在命令行补 `-p pytest_asyncio`；并设置 `PYTHONPATH=backend:.`。
- Backend Quick 下载超慢：
  - 解法：拆 `requirements_quick.txt` 去除大依赖；启用 pip 缓存（key 基于 `requirements` hash）。
- 文件检查一直 `None/Waiting`：
  - 现象：并发取消或刚排队。
  - 解法：等待当前 run 完成或在 UI 触发重跑；确认 job 名与分支保护配置一致。

**落地清单（今天即可执行）**
- 本地一键（四项快速闸门）：
  - `mypy --strict backend/app tests`
  - `PYTHONPATH=backend:. pytest -p pytest_asyncio -q -m smoke tests/smoke`
  - `cd frontend && npm ci && npm test -- --run src/__tests__/components src/__tests__/hooks src/__tests__/utils`
  - `python infrastructure/scripts/verify_structure.py || true`
- 远端策略：
  - 保留四个必需检查；Integration/覆盖率/性能改为合并后或定时跑。
  - `auto-merge (squash)` 开启；单人阶段 `main` 审批=0。

**里程碑**
- M1（今天）：四项快速闸门稳定 ≤10 分钟；首批 PR 自动合并串起来。
- M2（本周）：类型白名单收紧（业务代码 0 个 `# type: ignore`）、服务层异常治理（无 `except Exception`）。
- M3（两周）：Integration/覆盖率/性能基线在合并后稳定产出，主干稳定度提升。

**附录：现有关键文件位置**
- `/.github/workflows/test-quick.yml`：Quick Gate（已配置 `pytest_asyncio` 与 `PYTHONPATH`）。
- `/.github/workflows/file-check.yml`：文件管理质量检查。
- `/tests/pytest.ini`：pytest 项目级配置与标记。
- `/tests/smoke/`：后端冒烟用例（不依赖真实 DB）。

**附录：建议的 Make 目标（可选新增）**
- `make quick-gate-local`：一次跑完四项快速闸门（类型/后端/前端/文件检查）。
- `make backend-smoke`：只跑后端冒烟（自动设定 `PYTHONPATH` 与 `pytest_asyncio`）。

**说明**
- 本文档覆盖当前阶段的完整执行方案，默认以“先跑起来、快速收敛”为第一优先级；待进入多人协作与发布阶段，再逐步恢复更严格的门控与审批要求。
