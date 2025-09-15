## API v1 响应统一规范（第二批）

- 目标：端点显式 `response_model`，0 裸 `dict/list/JSONResponse`（流式响应除外）。
- 核心模型：`SuccessResponse { status, message, timestamp, data }`。

### SuccessResponse 结构
```json
{
  "status": "success",
  "message": "描述性消息",
  "timestamp": "2025-09-12T12:00:00Z",
  "data": { /* 端点数据载荷 */ }
}
```

### 监控端点（monitoring）

- GET `/api/v1/monitoring/tasks/{task_id}/history`
  - response_model: `List[TaskEvent]`
  - 返回示例（单项）：
    ```json
    {
      "task_id": "t1",
      "event_type": "status_change",
      "timestamp": "2025-09-12T12:00:00Z",
      "old_status": "pending",
      "new_status": "processing",
      "queue_name": "default",
      "metadata": {}
    }
    ```

- POST `/api/v1/monitoring/tasks/{task_id}/event`
  - response_model: `SuccessResponse`
  - data：`{"task_id": "..."}`

- POST `/api/v1/monitoring/tasks/batch-update`
  - response_model: `SuccessResponse`
  - data：`{"total": 10, "success": 9, "failed": 1}`

- POST `/api/v1/monitoring/maintenance/cleanup?days=30`
  - response_model: `SuccessResponse`
  - data：`{"cleaned_history": 5, "retention_days": 30}`

- GET `/api/v1/monitoring/workers`
  - response_model: `List[WorkerStatus]`

- GET `/api/v1/monitoring/queues`
  - response_model: `List[QueueMetrics]`

### 重试端点（retry）

- POST `/api/v1/retry/cleanup?older_than_days=30&dry_run=true`
  - response_model: `SuccessResponse`
  - data：
    ```json
    {
      "total_deleted": 12,
      "cutoff_date": "2025-08-13",
      "by_category": {"NETWORK_ERROR": 8, "PROCESSING_ERROR": 4},
      "dry_run": true,
      "cleanup_timestamp": "2025-09-12T12:00:00Z",
      "operator": "user-1",
      "operation_type": "dry_run"
    }
    ```

### 例外说明（保留）
- 流式响应（如 SSE、文件流）继续使用 `StreamingResponse`，不套 `SuccessResponse`。

### 验收清单
- 端点具备 `response_model`（SSE 除外）。
- 不再直接 `return {}`/`return []`。
- 新/改测试通过；lints/mypy 不新增错误。


