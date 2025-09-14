# 代码风格与约定（BTC/ETH 决策分析器 v2）

## 通用
- 使用 Python 3.11 类型注解；模块/函数/变量命名清晰，避免一字母命名。
- 数据契约以 `models.py` 中的 Pydantic v2 模型为准（`DecisionSignal`, `Candle`, `UserProgress`）。
- `DecisionSignal` 的 `skip` 一致性由 `model_validator` 强化：skip 时 side=skip 且 trigger/tp/sl 必须为 null。
- 不新增不必要的抽象，保持最小可行复杂度（Linus 式重构原则）。

## 后端
- 路由：FastAPI，端点应返回明确的 DTO；错误使用 `HTTPException`。
- 网络：优先异步 IO（httpx.AsyncClient）；若需同步库，使用 `run_in_executor` 包裹。
- 日志：开发期允许 `print`；生产期建议结构化日志与等级控制。
- A/B：`ab_testing.py` 管理；单实例 JSON 持久化，若多实例需锁/DB。
- 价格与触发：
  - 触发价 tick 对齐需按方向取整（long 向上、short 向下）。
  - ATR 自适应缓冲与最大触发距离护栏遵循 `config.py/HOTFIX_CONFIG`。

## 前端
- React + TS：组件拆分简洁（App/Chart/Decision）；
- 接口类型与后端 DTO 对齐；`api.ts` 统一调用，前端仅做展示与简单校验。
- API 基地址：优先 `VITE_API_BASE` 环境变量；本地默认 `http://localhost:8001`。
- WebSocket：心跳消息静默处理，断线重连退避 3s。

## 文档/PRD
- 文件位于 `docs/`；实现以 PRD 的 7 维信号与用户体验为基准。
- 灰度发布与监控策略遵循 `GRADUAL_ROLLOUT_GUIDE.md`。

## 提交/完成 Definition of Done（高层）
- 变更不破坏 7 维 DTO；关键路径（/signals/latest,/chart/candles,/ws）手测通过。
- 通过热修复验收脚本与基本性能脚本；主要接口 200 响应且无阻塞告警。
- 前端能显示实时价格、最新信号、图表线；无明显 UI 抖动/卡顿。