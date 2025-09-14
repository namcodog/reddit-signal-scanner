# 任务完成检查清单（BTC/ETH 决策分析器 v2）

- 功能对齐
  - [ ] 7 维信号契约未被破坏（skip 一致性校验通过）。
  - [ ] `/signals/latest` 返回时间 < 50ms（本地常规场景）。
  - [ ] `/chart/candles` 返回含 MA 数据，图表可渲染。
  - [ ] WebSocket 心跳+价格推送稳定，断线可重连。

- 兼容性与安全
  - [ ] 前端 `VITE_API_BASE` 可配置；后端 CORS 随环境收紧。
  - [ ] A/B 数据持久化无并发写冲突（单实例或加锁）。

- 基本验证
  - [ ] `python3 test_hotfix_v1.py` 通过。
  - [ ] `python3 test_performance.py` 通过或无回归。
  - [ ] 手动 `curl` 心跳/信号/图表/告警端点 200。

- 文档/记录
  - [ ] 关键改动在 `WORK_LOG.md` 或 PR 描述中说明。
  - [ ] 若涉及配置变更，补充 README/部署说明。
