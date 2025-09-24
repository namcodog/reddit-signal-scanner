# Backend 状态管理优先级清单（2025-09-23）

1. DemoAnalysisSimulator 状态机加固
   - 明确 pending→running→completed 阈值，确保 10s 内完成。
   - 支持 `DEMO_SIMULATOR_DURATION_SECONDS` 调整耗时，默认 10s。
   - 完成态固定 `completed_at` 与 `report_id`，供前端稳定消费。

2. 状态查询/轮询契约对齐
   - `/api/v1/status/{task_id}` fallback 模式补齐 `report_id`、`estimated_completion`。
   - TaskInfo 数据结构统一（SSE、HTTP、模拟器共用同一生成逻辑）。

3. 报告提取一致性
   - `/api/v1/report/{task_id}` 在模拟/真实模式保持 `task_id` 驱动。
   - TaskStatusService 完成态映射 `report_id`（如存在对应分析记录）。

4. 质量护栏
   - 为模拟器与状态端点补充分层测试，验证状态推进与完成态。
   - 修复交付流程默认跑后端类型检查与 smoke。
