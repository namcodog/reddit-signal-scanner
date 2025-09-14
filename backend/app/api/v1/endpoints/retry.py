"""
任务重试管理API端点

提供死信队列管理和手动重试功能：
- 死信队列查询和统计
- 手动重试接口
- 批量重试操作
- 失败分析报告

Linus原则应用：
1. 数据结构决定一切 - 清晰的请求/响应模型
2. 消除特殊情况 - 统一的错误处理和响应格式
3. 简单胜过聪明 - 直观的RESTful API设计
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Union, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from ....core.auth import authenticate_user as get_current_user
from ....core.database import get_db
from ....core.sqlalchemy_typing import as_bool_clause
from ....models.task import Task, TaskStatus
from ....models.user import User
from ....schemas.common.responses import ResponseStatus, SuccessResponse
from ....services.failure_analyzer import get_failure_analyzer
from ....tasks.dead_letter_handler import (
    DeadLetterQueryFilter,
    ManualRetryRequest,
    get_dead_letter_handler,
)

# 创建重试管理路由
router = APIRouter(prefix="/retry", tags=["任务重试"])


# ===== 请求/响应模型 =====


class DeadLetterQueryRequest(BaseModel):
    """死信队列查询请求"""

    failure_categories: Optional[List[str]] = None
    age_hours_min: Optional[int] = None
    age_hours_max: Optional[int] = None
    retry_count_min: Optional[int] = None
    retry_count_max: Optional[int] = None
    limit: int = 50
    offset: int = 0

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v: int) -> int:
        if v < 1 or v > 1000:
            raise ValueError("limit必须在1-1000之间")
        return v


class BatchRetryRequest(BaseModel):
    """批量重试请求"""

    task_ids: List[str]
    retry_immediately: bool = False
    reason: str = "manual_batch_retry"

    @field_validator("task_ids")
    @classmethod
    def validate_task_ids(cls, v: List[str]) -> List[str]:
        if not v or len(v) > 100:
            raise ValueError("task_ids不能为空且不能超过100个")
        return v


class TaskRetryInfo(BaseModel):
    """任务重试信息"""

    task_id: str
    user_id: str
    status: str
    retry_count: int
    failure_category: Optional[str]
    error_message: Optional[str]
    dead_letter_at: Optional[str]
    last_retry_at: Optional[str]
    created_at: str


class DeadLetterResponse(BaseModel):
    """死信队列响应"""

    total_count: int
    tasks: List[TaskRetryInfo]
    has_more: bool
    query_filters: Dict[str, Optional[Union[str, int, List[str]]]]


class RetryOperationResponse(BaseModel):
    """重试操作响应"""

    operation_id: str
    total_requested: int
    successful_retries: int
    failed_retries: int
    success_task_ids: List[str]
    failed_tasks: List[Dict[str, str]]
    retry_timestamp: str


class FailureAnalysisResponse(BaseModel):
    """失败分析响应"""

    time_window_hours: int
    failure_by_category: Dict[str, int]
    total_failures: int
    alerts: List[Dict[str, Union[str, int, bool, List[str]]]]
    preventive_suggestions: List[Dict[str, Union[str, int]]]
    analysis_timestamp: str


class UserRetryStats(BaseModel):
    dead_letter_count: int
    tasks_with_retries: int
    user_id: str


class SystemRetryStats(BaseModel):
    total_dead_letter: int
    by_category: Dict[str, int]
    by_age: Dict[str, int]
    avg_failure_count: float


class RetryStatisticsResponse(BaseModel):
    user_statistics: UserRetryStats
    system_statistics: SystemRetryStats


# ===== API端点实现 =====


@router.get(
    "/dead-letter",
    response_model=DeadLetterResponse,
    summary="查询死信队列",
    description="查询用户的死信队列中的任务，支持多种过滤条件",
)
async def get_dead_letter_queue(
    failure_categories: Optional[str] = Query(None, description="失败类型过滤，逗号分隔"),
    age_hours_min: Optional[int] = Query(None, description="最小存在小时数"),
    age_hours_max: Optional[int] = Query(None, description="最大存在小时数"),
    retry_count_min: Optional[int] = Query(None, description="最小重试次数"),
    retry_count_max: Optional[int] = Query(None, description="最大重试次数"),
    limit: int = Query(50, description="返回数量限制"),
    offset: int = Query(0, description="偏移量"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeadLetterResponse:
    """查询当前用户的死信队列任务"""

    try:
        # 构建查询过滤器
        filters = DeadLetterQueryFilter(
            failure_categories=(
                failure_categories.split(",") if failure_categories else None
            ),
            age_hours_min=age_hours_min,
            age_hours_max=age_hours_max,
            retry_count_min=retry_count_min,
            retry_count_max=retry_count_max,
            user_id=str(current_user.id),  # 只查询当前用户的任务
        )

        # 获取死信队列处理器
        dlq_handler = get_dead_letter_handler()

        # 查询死信任务
        tasks, total_count = dlq_handler.get_dead_letter_tasks(
            db, filters, limit, offset
        )

        # 转换为响应格式
        task_infos = []
        for task in tasks:
            task_info = TaskRetryInfo(
                task_id=str(task.id),
                user_id=str(task.user_id),
                status=task.status,
                retry_count=task.retry_count,
                failure_category=task.failure_category,
                error_message=task.error_message,
                dead_letter_at=(
                    task.dead_letter_at.isoformat() if task.dead_letter_at else None
                ),
                last_retry_at=(
                    task.last_retry_at.isoformat() if task.last_retry_at else None
                ),
                created_at=task.created_at.isoformat(),
            )
            task_infos.append(task_info)

        return DeadLetterResponse(
            total_count=total_count,
            tasks=task_infos,
            has_more=offset + limit < total_count,
            query_filters={
                "failure_categories": filters.failure_categories,
                "age_hours_min": age_hours_min,
                "age_hours_max": age_hours_max,
                "retry_count_min": retry_count_min,
                "retry_count_max": retry_count_max,
                "limit": limit,
                "offset": offset,
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询死信队列失败: {str(e)}")


@router.post(
    "/manual",
    response_model=RetryOperationResponse,
    summary="手动重试任务",
    description="手动重试死信队列中的指定任务",
)
async def manual_retry_tasks(
    retry_request: BatchRetryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RetryOperationResponse:
    """手动重试指定的死信任务"""

    try:
        # 验证任务所有权 - 只能重试自己的任务
        task_uuids = []
        for task_id in retry_request.task_ids:
            try:
                task_uuid = UUID(task_id)
                task_uuids.append(str(task_uuid))
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的任务ID格式: {task_id}")

        # 验证任务所有权
        owned_tasks = (
            db.query(Task)
            .filter(
                as_bool_clause(Task.id.in_(task_uuids)),
                as_bool_clause(Task.user_id == current_user.id),
            )
            .count()
        )

        if owned_tasks != len(task_uuids):
            raise HTTPException(status_code=403, detail="只能重试自己的任务")

        # 构建重试请求
        manual_request = ManualRetryRequest(
            task_ids=task_uuids,
            retry_immediately=retry_request.retry_immediately,
            reason=retry_request.reason,
        )

        # 执行重试操作
        dlq_handler = get_dead_letter_handler()
        result = dlq_handler.manual_retry_tasks(db, manual_request)

        # 生成操作ID
        from datetime import datetime

        operation_id = (
            f"retry_{current_user.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        )

        # 失败任务从 List[Tuple[str, str]] 收敛为 List[Dict[str, str]]
        failed_tasks_dicts: List[Dict[str, str]] = [
            {"task_id": t[0], "reason": t[1]} for t in result["failed_tasks"]
        ]

        return RetryOperationResponse(
            operation_id=operation_id,
            total_requested=int(result["total_requested"]),
            successful_retries=int(result["successful_retries"]),
            failed_retries=int(result["failed_retries"]),
            success_task_ids=result["success_task_ids"],
            failed_tasks=failed_tasks_dicts,
            retry_timestamp=str(result["retry_timestamp"]),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"手动重试失败: {str(e)}")


@router.get(
    "/statistics",
    response_model=RetryStatisticsResponse,
    summary="获取重试统计",
    description="获取用户的重试和死信队列统计信息",
)
async def get_retry_statistics(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> RetryStatisticsResponse:
    """获取当前用户的重试统计信息"""

    try:
        # 获取死信队列统计
        dlq_handler = get_dead_letter_handler()
        dlq_stats = dlq_handler.get_dead_letter_statistics(db)

        # 获取用户相关的统计（需要过滤）
        user_dlq_count = (
            db.query(Task)
            .filter(
                as_bool_clause(Task.user_id == current_user.id),
                as_bool_clause(Task.status == TaskStatus.DEAD_LETTER.value),
            )
            .count()
        )

        user_retry_count = (
            db.query(Task)
            .filter(
                as_bool_clause(Task.user_id == current_user.id),
                as_bool_clause(Task.retry_count > 0),
            )
            .count()
        )

        return RetryStatisticsResponse(
            user_statistics=UserRetryStats(
                dead_letter_count=user_dlq_count,
                tasks_with_retries=user_retry_count,
                user_id=str(current_user.id),
            ),
            system_statistics=SystemRetryStats(
                total_dead_letter=dlq_stats.total_count,
                by_category=dlq_stats.by_category,
                by_age=dlq_stats.by_age,
                avg_failure_count=dlq_stats.avg_failure_count,
            ),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get(
    "/failure-analysis",
    response_model=FailureAnalysisResponse,
    summary="获取失败分析",
    description="获取失败模式分析和预防建议",
)
async def get_failure_analysis(
    time_window_hours: int = Query(24, description="分析时间窗口(小时)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FailureAnalysisResponse:
    """获取失败模式分析和预防建议"""

    try:
        # 获取失败分析器
        analyzer = get_failure_analyzer()

        # 获取失败统计
        failure_stats = analyzer.get_failure_statistics(db, time_window_hours)

        # 获取预防性建议
        preventive_suggestions = analyzer.suggest_preventive_actions(db)

        return FailureAnalysisResponse(
            time_window_hours=int(time_window_hours),
            failure_by_category=cast(
                Dict[str, int], failure_stats["failure_by_category"]
            ),
            total_failures=cast(int, failure_stats["total_failures"]),
            alerts=cast(
                List[Dict[str, Union[str, int, bool, List[str]]]],
                failure_stats["alerts"],
            ),
            preventive_suggestions=preventive_suggestions,
            analysis_timestamp=cast(str, failure_stats["analysis_timestamp"]),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取失败分析失败: {str(e)}")


@router.post(
    "/cleanup",
    response_model=SuccessResponse,
    summary="清理旧的死信任务",
    description="清理指定天数前的死信任务（管理员功能）",
)
async def cleanup_old_dead_letters(
    older_than_days: int = Query(30, description="清理多少天前的记录"),
    dry_run: bool = Query(True, description="是否为试运行"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuccessResponse:
    """清理旧的死信任务（仅限管理员）"""

    # TODO: 添加管理员权限检查
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        dlq_handler = get_dead_letter_handler()

        # 执行清理操作
        cleanup_result = dlq_handler.cleanup_old_dead_letters(
            db, older_than_days, dry_run
        )

        current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        # 扁平化返回，作为 SuccessResponse.data
        return SuccessResponse(
            status=ResponseStatus.SUCCESS,
            message="死信清理完成",
            timestamp=current_time,
            data={
                "total_deleted": int(cleanup_result["total_deleted"]),
                "cutoff_date": str(cleanup_result["cutoff_date"]),
                "by_category": cleanup_result["by_category"],
                "dry_run": bool(cleanup_result["dry_run"]),
                "cleanup_timestamp": str(cleanup_result["cleanup_timestamp"]),
                "operator": str(current_user.id),
                "operation_type": "dry_run" if dry_run else "actual_cleanup",
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理操作失败: {str(e)}")
