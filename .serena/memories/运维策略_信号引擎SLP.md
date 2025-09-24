## 运维要求（信号引擎 V2 + SLP）
- 每日 UTC 00:05 离线回放 72h 1m 行情+信号：`python bt_min/backtest_min.py --config bt_min/config.json`。
- 监控指标：TTL MAE≤6、PI80 覆盖率 75~90%、强信号占比≥5%、tradeable 在 35~45%、触发距离≤0.6%。
- 配置关键值：`strong_min=65`、`sqs_actionable_min=45`、压缩扣分10、`slp.enabled=true`。
- 在线监控：`monitor_v2_24h.sh` 每5分钟抓 `/monitoring/stats`，符合报警阈值即通知。
- 灰度策略：SLP V1 分档 10%→30%→100%，每档 24h 达标再推。
- 日报内容：回测收益/回撤、TTL 质量、闸门原因分布、在线告警、配置变更。
- 异常处理：TTL 指标退回 V0；闸门过松/过紧调参数；接口异常重启后端。
