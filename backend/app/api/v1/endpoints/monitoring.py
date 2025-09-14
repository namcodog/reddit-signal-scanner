"""
监控API端点 - 提供任务状态和系统监控接口

基于Linus原则：
1. RESTful设计 - 统一的资源访问模式
2. 清晰的错误处理 - 降级机制
3. 100%类型覆盖 - 类型安全
"""

import logging
from datetime import datetime, timezone
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Protocol,
    cast,
    runtime_checkable,
)

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import JSONResponse

from app.core.task_status import UnifiedTaskStatus
from app.schemas.common.responses import ResponseStatus, SuccessResponse
from app.schemas.task_monitor import (
    Alert,
    QueueMetrics,
    SystemHealthResponse,
    TaskEvent,
    TaskQueryRequest,
    TaskQueryResponse,
    TaskSnapshot,
    TaskStatsRequest,
    TaskStatsResponse,
    WorkerStatus,
)

from ....core.types import JsonValue


# 协议类型：为动态注入的依赖提供最小可用类型约束
@runtime_checkable
class TaskTrackerProtocol(Protocol):
    def get_task_status(self, task_id: str) -> TaskSnapshot:
        ...

    def query_tasks(self, request: TaskQueryRequest) -> TaskQueryResponse:
        ...

    def get_task_history(self, task_id: str, limit: int) -> List[dict[str, JsonValue]]:
        ...

    def process_event(self, event: TaskEvent) -> bool:
        ...

    def batch_update_status(
        self,
        task_ids: List[str],
        new_status: UnifiedTaskStatus,
        worker_id: Optional[str] = None,
    ) -> int:
        ...

    def cleanup_old_history(self, days: int) -> int:
        ...


@runtime_checkable
class SystemMonitorProtocol(Protocol):
    async def get_system_health(self) -> SystemHealthResponse:
        ...

    async def get_all_workers(self) -> List[Any]:
        ...

    def get_all_queues(self) -> List[Any]:
        ...


@runtime_checkable
class AlertProcessorProtocol(Protocol):
    def get_active_alerts(self) -> List[Alert]:
        ...

    def resolve_alert(self, alert_id: str) -> bool:
        ...

    def get_alert_history(self, limit: int) -> List[dict[str, JsonValue]]:
        ...


# 懒加载服务依赖，避免缺失模块导致启动失败
def _get_task_tracker() -> Optional[TaskTrackerProtocol]:
    try:
        from app.services.task_tracker import get_task_tracker

        return cast(TaskTrackerProtocol, get_task_tracker())
    except Exception as e:  # ImportError 或其他错误
        logger.warning(f"任务跟踪服务不可用: {e}")
        return None


def _get_system_monitor() -> Optional[SystemMonitorProtocol]:
    try:
        from app.services.task_monitor import get_system_monitor

        return cast(SystemMonitorProtocol, get_system_monitor())
    except Exception as e:
        logger.warning(f"系统监控服务不可用: {e}")
        return None


def _get_alert_processor() -> Optional[AlertProcessorProtocol]:
    try:
        from app.services.alert_processor import get_alert_processor

        return cast(AlertProcessorProtocol, get_alert_processor())
    except Exception as e:
        logger.warning(f"告警处理器不可用: {e}")
        return None


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["监控管理"])


# ==================== 任务状态查询 ====================


@router.get("/tasks/{task_id}/status", response_model=TaskSnapshot)
async def get_task_status(task_id: str = Path(..., description="任务ID")) -> TaskSnapshot:
    """
    获取单个任务状态

    降级策略：Redis → Database
    """
    try:
        tracker = _get_task_tracker()
        if tracker is None:
            raise HTTPException(status_code=503, detail="任务跟踪服务不可用")
        snapshot = tracker.get_task_status(task_id)

        if not snapshot:
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

        return snapshot

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务状态失败: {task_id}, 错误: {e}")
        raise HTTPException(status_code=500, detail="获取任务状态失败")


@router.post("/tasks/query", response_model=TaskQueryResponse)
async def query_tasks(request: TaskQueryRequest) -> TaskQueryResponse:
    """
    查询任务列表

    支持多维度过滤和分页
    """
    try:
        tracker = _get_task_tracker()
        if tracker is None:
            raise HTTPException(status_code=503, detail="任务跟踪服务不可用")
        response = tracker.query_tasks(request)
        return response

    except Exception as e:
        logger.error(f"查询任务失败: {e}")
        raise HTTPException(status_code=500, detail="查询任务失败")


@router.get("/tasks/{task_id}/history", response_model=List[TaskEvent])
async def get_task_history(
    task_id: str = Path(..., description="任务ID"),
    limit: int = Query(20, ge=1, le=100, description="历史记录数量"),
) -> List[TaskEvent]:
    """获取任务状态变更历史"""
    try:
        tracker = _get_task_tracker()
        if tracker is None:
            raise HTTPException(status_code=503, detail="任务跟踪服务不可用")
        history = tracker.get_task_history(task_id, limit)

        if not history:
            return []

        # 将历史记录统一为强类型模型
        events: List[TaskEvent] = []
        for item in history:
            # 显式字段收敛，避免 **item 触发不匹配
            ts = item.get("timestamp")
            timestamp = ts if isinstance(ts, datetime) else datetime.now(timezone.utc)

            old_s = item.get("old_status")
            old_status = old_s if isinstance(old_s, UnifiedTaskStatus) else None

            new_s = item.get("new_status")
            new_status = (
                new_s if isinstance(new_s, UnifiedTaskStatus) else UnifiedTaskStatus.PENDING
            )

            meta = item.get("metadata")
            metadata: Dict[str, JsonValue] = meta if isinstance(meta, dict) else {}

            events.append(
                TaskEvent(
                    task_id=str(item.get("task_id", "")),
                    event_type=str(item.get("event_type", "status_update")),
                    timestamp=timestamp,
                    old_status=old_status,
                    new_status=new_status,
                    user_id=(str(item.get("user_id")) if item.get("user_id") is not None else None),
                    worker_id=(str(item.get("worker_id")) if item.get("worker_id") is not None else None),
                    queue_name=str(item.get("queue_name", "default")),
                    metadata=metadata,
                    error_message=(str(item.get("error_message")) if item.get("error_message") is not None else None),
                )
            )
        return events

    except Exception as e:
        logger.error(f"获取任务历史失败: {task_id}, 错误: {e}")
        raise HTTPException(status_code=500, detail="获取任务历史失败")


@router.post("/tasks/{task_id}/event", response_model=SuccessResponse)
async def process_task_event(
    event: TaskEvent, task_id: str = Path(..., description="任务ID")
) -> SuccessResponse:
    """
    处理任务事件

    用于手动更新任务状态或Worker回调
    """
    try:
        # 确保事件的task_id一致
        event.task_id = task_id

        tracker = _get_task_tracker()
        if tracker is None:
            raise HTTPException(status_code=503, detail="任务跟踪服务不可用")
        success = tracker.process_event(event)

        if not success:
            raise HTTPException(status_code=400, detail="事件处理失败")

        current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return SuccessResponse(
            status=ResponseStatus.SUCCESS,
            message="事件处理成功",
            timestamp=current_time,
            data={"task_id": task_id},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理任务事件失败: {task_id}, 错误: {e}")
        raise HTTPException(status_code=500, detail="处理任务事件失败")


# ==================== 任务统计 ====================


@router.post("/tasks/stats", response_model=TaskStatsResponse)
async def get_task_stats(request: TaskStatsRequest) -> TaskStatsResponse:
    """获取任务统计信息"""
    try:
        tracker = _get_task_tracker()
        if tracker is None:
            raise HTTPException(status_code=503, detail="任务跟踪服务不可用")

        # 构建查询请求
        query_request = TaskQueryRequest(
            user_id=request.user_id,
            queue_name=request.queue_name,
            start_date=request.start_date,
            end_date=request.end_date,
            limit=1000,  # 统计使用较大的限制
        )

        response = tracker.query_tasks(query_request)

        # 统计各状态任务数
        total_tasks = response.total
        pending_tasks = sum(
            1 for t in response.tasks if t.status == UnifiedTaskStatus.PENDING
        )
        processing_tasks = sum(
            1 for t in response.tasks if t.status == UnifiedTaskStatus.PROCESSING
        )
        completed_tasks = sum(
            1 for t in response.tasks if t.status == UnifiedTaskStatus.COMPLETED
        )
        failed_tasks = sum(
            1 for t in response.tasks if t.status == UnifiedTaskStatus.FAILED
        )

        # 计算成功率
        finished_tasks = completed_tasks + failed_tasks
        success_rate = (
            (completed_tasks / finished_tasks * 100) if finished_tasks > 0 else 0
        )

        # 计算平均处理时间
        processing_times = []
        for task in response.tasks:
            if task.started_at and task.completed_at:
                duration = (task.completed_at - task.started_at).total_seconds()
                processing_times.append(duration)

        avg_processing_time = (
            sum(processing_times) / len(processing_times) if processing_times else 0
        )
        max_processing_time = max(processing_times) if processing_times else 0

        return TaskStatsResponse(
            total_tasks=total_tasks,
            pending_tasks=pending_tasks,
            processing_tasks=processing_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            success_rate=success_rate,
            avg_processing_time=avg_processing_time,
            max_processing_time=max_processing_time,
            period=request.period,
        )

    except Exception as e:
        logger.error(f"获取任务统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取任务统计失败")


# ==================== 系统健康监控 ====================


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health() -> SystemHealthResponse:
    """
    获取系统健康状态

    包括Worker状态、队列指标、活跃告警
    """
    try:
        monitor = _get_system_monitor()
        if monitor is None:
            return SystemHealthResponse(
                workers=[],
                queues=[],
                active_alerts=[],
                total_workers=0,
                healthy_workers=0,
                total_queues=0,
                system_status="unknown",
            )
        health = await monitor.get_system_health()

        # 获取活跃告警
        processor = _get_alert_processor()
        if processor is None:
            health.active_alerts = []
            return health
        active_alerts = processor.get_active_alerts()
        health.active_alerts = active_alerts

        return health

    except Exception as e:
        logger.error(f"获取系统健康状态失败: {e}")
        # 降级响应
        return SystemHealthResponse(
            workers=[],
            queues=[],
            active_alerts=[],
            total_workers=0,
            healthy_workers=0,
            total_queues=0,
            system_status="unknown",
        )


@router.get("/workers", response_model=List[WorkerStatus])
async def get_workers() -> List[WorkerStatus]:
    """获取所有Worker状态"""
    try:
        monitor = _get_system_monitor()
        if monitor is None:
            return []
        workers = await monitor.get_all_workers()

        return list(workers)

    except Exception as e:
        logger.error(f"获取Worker状态失败: {e}")
        raise HTTPException(status_code=500, detail="获取Worker状态失败")


@router.get("/queues", response_model=List[QueueMetrics])
async def get_queues() -> List[QueueMetrics]:
    """获取所有队列指标"""
    try:
        monitor = _get_system_monitor()
        if monitor is None:
            return []
        queues = monitor.get_all_queues()

        return list(queues)

    except Exception as e:
        logger.error(f"获取队列指标失败: {e}")
        raise HTTPException(status_code=500, detail="获取队列指标失败")


# ==================== 告警管理 ====================


@router.get("/alerts/active", response_model=List[Alert])
async def get_active_alerts() -> List[Alert]:
    """获取活跃告警列表"""
    try:
        processor = _get_alert_processor()
        if processor is None:
            return []
        alerts = processor.get_active_alerts()
        return list(alerts)

    except Exception as e:
        logger.error(f"获取活跃告警失败: {e}")
        raise HTTPException(status_code=500, detail="获取活跃告警失败")


@router.post("/alerts/{alert_id}/resolve", response_model=SuccessResponse)
async def resolve_alert(
    alert_id: str = Path(..., description="告警ID")
) -> SuccessResponse:
    """解决告警"""
    try:
        processor = _get_alert_processor()
        if processor is None:
            current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            return SuccessResponse(
                status=ResponseStatus.SUCCESS,
                message="告警处理器不可用，执行降级返回",
                timestamp=current_time,
                data={"alert_id": alert_id, "resolved": False},
            )
        success = processor.resolve_alert(alert_id)

        if not success:
            raise HTTPException(status_code=400, detail="解决告警失败")

        current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return SuccessResponse(
            status=ResponseStatus.SUCCESS,
            message="告警已解决",
            timestamp=current_time,
            data={"alert_id": alert_id, "resolved": True},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"解决告警失败: {alert_id}, 错误: {e}")
        raise HTTPException(status_code=500, detail="解决告警失败")


@router.get("/alerts/history")
async def get_alert_history(
    limit: int = Query(100, ge=1, le=1000, description="历史记录数量")
) -> list[dict[str, JsonValue]]:
    """获取告警历史"""
    try:
        processor = _get_alert_processor()
        if processor is None:
            return []
        history = processor.get_alert_history(limit)
        return list(history)

    except Exception as e:
        logger.error(f"获取告警历史失败: {e}")
        raise HTTPException(status_code=500, detail="获取告警历史失败")


# ==================== 批量操作 ====================


@router.post("/tasks/batch-update", response_model=SuccessResponse)
async def batch_update_tasks(
    task_ids: List[str], new_status: UnifiedTaskStatus, worker_id: Optional[str] = None
) -> SuccessResponse:
    """批量更新任务状态"""
    try:
        tracker = _get_task_tracker()
        if tracker is None:
            raise HTTPException(status_code=503, detail="任务跟踪服务不可用")
        success_count = tracker.batch_update_status(task_ids, new_status, worker_id)

        current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return SuccessResponse(
            status=ResponseStatus.SUCCESS,
            message="批量更新任务状态完成",
            timestamp=current_time,
            data={
                "total": len(task_ids),
                "success": success_count,
                "failed": len(task_ids) - success_count,
            },
        )

    except Exception as e:
        logger.error(f"批量更新任务失败: {e}")
        raise HTTPException(status_code=500, detail="批量更新任务失败")


@router.post("/maintenance/cleanup", response_model=SuccessResponse)
async def cleanup_old_data(
    days: int = Query(30, ge=7, le=90, description="清理多少天前的数据")
) -> SuccessResponse:
    """清理旧数据"""
    try:
        tracker = _get_task_tracker()
        if tracker is None:
            current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            return SuccessResponse(
                status=ResponseStatus.SUCCESS,
                message="任务跟踪服务不可用，执行降级返回",
                timestamp=current_time,
                data={"cleaned_history": 0, "retention_days": days},
            )
        cleaned_count = tracker.cleanup_old_history(days)

        current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return SuccessResponse(
            status=ResponseStatus.SUCCESS,
            message="历史数据清理完成",
            timestamp=current_time,
            data={
                "cleaned_history": cleaned_count,
                "retention_days": days,
            },
        )

    except Exception as e:
        logger.error(f"清理数据失败: {e}")
        raise HTTPException(status_code=500, detail="清理数据失败")
