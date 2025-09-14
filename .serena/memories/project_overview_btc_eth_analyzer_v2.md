# 项目概览（BTC/ETH 决策分析器 v2）

- 目标：将复杂的K线分析简化为可执行的 7 维决策信号（买/卖/观望、触发价、TP、SL、强度、杠杆、有效期等），并通过极简前端实时展示。
- 核心价值：
  - 大白话输出，给出明确的“触发价/止损/止盈”数字。
  - 实时（<2s）信号与价格流；A/B 灰度发布与阈值监控。
- 运行环境：Darwin/macOS，本地开发。

## 技术栈
- 后端：Python 3.11、FastAPI、Uvicorn、Pydantic v2、WebSocket、（当前 requests；建议迁移 httpx.AsyncClient）。
- 前端：React + Vite + TypeScript、axios、lightweight-charts。
- 依赖：
  - backend/requirements.txt：fastapi、uvicorn、websockets、pydantic。
  - frontend/package.json：react、react-dom、lightweight-charts、axios。

## 代码结构（关键）
- `btc-eth-analyzer-v2/backend/`
  - `main.py`：FastAPI 应用与路由（/signals/latest, /chart/candles, /ws/stream/candles 等），OKX 数据抓取、历史信号、A/B、监控、WS 推流。
  - `engine.py`：决策引擎（MA/ATR 自适应、触发价 A/B 方案、杠杆建议等）。
  - `models.py`：Pydantic 数据模型（DecisionSignal, Candle, UserProgress）。
  - `config.py`：算法/系统配置与 D+2 调参补丁配置。
  - `ab_testing.py`、`monitoring.py`、`threshold_monitor.py`、`rollback_monitor.py`：A/B 实验、监控与回滚。
  - `test_hotfix_v1.py`、`test_performance.py`、`test_server.py`：验收/性能/模拟服务脚本。
- `btc-eth-analyzer-v2/frontend/`
  - `src/App.tsx`、`Chart.tsx`、`Decision.tsx`、`api.ts`：单页应用，实时连接后端 WebSocket/HTTP。
- `docs/`：PRD 与重构计划、部署/灰度指南等。

## 约束与接口（后端）
- 主要端点：
  - `GET /signals/latest?symbol=BTCUSDT&timeframe=5m&force_refresh=false&user_id=optional`
  - `GET /chart/candles?symbol=BTCUSDT&timeframe=5m&limit=200`
  - `GET /price/realtime?symbol=BTCUSDT`
  - `POST /user/day-progress`（接收完整 `UserProgress`）
  - `GET /ws/stream/candles`（WebSocket 心跳+价格推送）
  - 监控相关：`/monitoring/*`, `/ab-test/*`, `/rollback/check`

## 当前已知风险/注意点
- OKX 调用使用 `requests` 同步API，可能阻塞事件循环（建议迁移至 `httpx.AsyncClient`）。
- 前端提交的收益接口与后端 `UserProgress` 模型不一致（需对齐）。
- A/B 结果落地 JSON 文件，若多进程需要文件锁或迁移 sqlite。
- CORS 目前为 `*`（开发便捷，生产需收紧）。

## 预期开发流
- 后端启动 -> 前端启动 -> 打开浏览器 -> 获取信号/图表/实时价格 -> A/B 与监控持续收集数据。

> 本条目用于 Serena 独立项目上下文，请勿与其他仓库（如 reddit 项目）混用。