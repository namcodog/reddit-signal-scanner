# 最小化 Navigator 极速上手手册

## 项目概述
- Reddit Signal Scanner：后端 Python 3.11 + 前端 TypeScript，workflow 工具拆 8 大 PRD，共 69 个原子任务。
- 使命：技术债止血 + 快速交付；质量闸门（Quick Gate）必须 <10 分钟给答复。
- Claude Code 是主控台，Makefile 与 workflow.py 提供一键式操作面板。

## Setup Commands（先把地基打牢）
1. `make install`：后端创建 `backend/venv` 并装 requirements，前端/管理端一并 `npm install`。
2. `make env-check`：确认 Python 3.11 与关键依赖版本；异常立刻修正。
3. `python workflow.py status`：掌握今日任务排班，避免撞车。
4. 大扫除：`make clean-all`（危险操作，会清空依赖，按 Y 才会执行）。

## 构建和测试命令（常用速查）
- 后端冒烟：`make test-smoke` 或 `make backend-smoke`（聚焦 `tests/smoke`）。
- 全量单测：`make test`（后端 pytest + 前端 npm test）。
- 类型铁拳：`make type-check`（MyPy 严格模式），前端执行 `npm run type-check` 与 `npm run lint`。
- 快速四件套：`make quick-gate-local`（类型 + backend smoke + frontend 组件集 + 文件检查）。
- CI 脚本：`python3 tests/ci/test_runner.py <lint|type|test|integration|perf>`。

## Code Style（写得帅又不挨打）
- Python：所有函数/变量写全量类型；禁止 `Dict[str, Any]` 与裸 `Any`；业务代码 0 个 `# type: ignore`；用 `TypedDict` 或 Pydantic 表达结构。
- TypeScript/TSX：strict 模式；组件 Props 必须接口化；禁 `any`、`Record<string, any>`；测试文件仅允许 mock 函数用 `any`。
- 格式：后端走 `black`+`isort`，前端走 `eslint`+`prettier`；必要时 `make fix-format`。
- 提交前跑 `pre-commit run --all-files`，免得质量门给你红灯。

## Testing Instructions（别等 CI 告状）
- 新功能：至少通过 `make quick-gate-local`，确保类型、后端 smoke、前端关键单测、文件结构检查全绿。
- 回归：系统/集成依赖服务时用 `python3 tests/ci/test_runner.py integration`；性能回归跑 `make ci-perf-gate PREV=/path/to/baseline.json`。
- 结果标准：pytest 0 失败、vitest 稳定、MyPy 严格零报错、lint 0 warning。
- 定位失败：到对应目录重跑（例：`cd backend && ./venv/bin/pytest -k smoke`），修复后再 rerun 全量命令。

## PR Instructions（让 Reviewer 秒点通过）
- 分支策略：日常从 `develop` 切任务分支；合入依赖 Auto-merge，务必确保 Quick Gate、Type Check、文件检查全绿。
- 提交节奏：小步提交 + `git status` 保证无脏文件；必要时拆 PR 避免超大 diff。
- PR 描述建议：
  1. 背景/问题
  2. 解决方案 & 关键改动
  3. 验收结果（贴命令：`make quick-gate-local` ✅）
  4. 风险与回滚计划
- 发起前 Checklist：无新 `except Exception`，类型白名单未突破，pre-commit 全绿，相关文档同步更新。

## 安全注意事项（安全第一不翻车）
- 不要把密钥、TOKEN 写进仓库或日志；本地配置用 `.env.local` 或环境变量。
- 清理脚本（`make clean-*`）会删除缓存与依赖，执行前确认路径，避免误删手工文件。
- 引入第三方库前先评估许可证与安全公告；升级依赖后务必跑 `make quick-gate-local`。
- 数据脱敏：调试日志请去掉用户/业务敏感字段，再提交。
