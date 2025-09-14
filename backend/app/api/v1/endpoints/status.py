"""
Reddit Signal Scanner - 任务状态查询端点

Linus原则："提供fallback，永不破坏用户体验"
- 为SSE流提供轮询fallback
- 简单的GET请求，更好的兼容性
- 统一的状态格式
- 真实数据库查询替代Mock实现
"""

import hashlib
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.fallback import get_client_guidance, get_fallback_config
from app.schemas.common.responses import ResponseStatus, SuccessResponse
from app.schemas.task import TaskInfo, TaskStatus
from app.services.task_status_service import TaskStatusService

router = APIRouter(prefix="/status", tags=["任务状态"])


def _generate_mock_seed(task_id: str) -> int:
    """生成Mock状态的安全种子值"""
    task_hash = hashlib.sha256(f"mock_status_{task_id}".encode()).hexdigest()
    return int(task_hash[:8], 16) % 10000


def _get_current_timestamp() -> str:
    """获取当前时间戳"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _create_pending_task_info(task_id: str, current_time: str) -> TaskInfo:
    """创建PENDING状态的TaskInfo"""
    return TaskInfo(
        task_id=task_id,
        status=TaskStatus.PENDING,
        progress=0,
        created_at=current_time,
        updated_at=current_time,
        estimated_completion=time.strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime(time.time() + 300)  # 5分钟后
        ),
    )


def _create_running_task_info(
    task_id: str, seed_value: int, current_time: str
) -> TaskInfo:
    """创建RUNNING状态的TaskInfo"""
    progress = ((seed_value // 10) % 80) + 10  # 10-90范围
    return TaskInfo(
        task_id=task_id,
        status=TaskStatus.RUNNING,
        progress=progress,
        created_at=current_time,
        updated_at=current_time,
        estimated_completion=time.strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime(time.time() + (100 - progress) * 3)
        ),
    )


def _create_completed_task_info(task_id: str, current_time: str) -> TaskInfo:
    """创建COMPLETED状态的TaskInfo"""
    return TaskInfo(
        task_id=task_id,
        status=TaskStatus.COMPLETED,
        progress=100,
        created_at=current_time,
        updated_at=current_time,
    )


def _create_failed_task_info(
    task_id: str, seed_value: int, current_time: str
) -> TaskInfo:
    """创建FAILED状态的TaskInfo"""
    return TaskInfo(
        task_id=task_id,
        status=TaskStatus.FAILED,
        progress=((seed_value // 100) % 60) + 20,  # 20-80范围
        created_at=current_time,
        updated_at=current_time,
        error_message="Mock错误：Reddit API连接超时",
    )


def get_mock_task_status(task_id: str) -> TaskInfo:
    """获取Mock任务状态 - 简化版本"""
    seed_value = _generate_mock_seed(task_id)
    status_choice = (seed_value % 10) + 1
    current_time = _get_current_timestamp()

    if status_choice <= 2:
        return _create_pending_task_info(task_id, current_time)
    elif status_choice <= 6:
        return _create_running_task_info(task_id, seed_value, current_time)
    elif status_choice <= 8:
        return _create_completed_task_info(task_id, current_time)
    else:
        return _create_failed_task_info(task_id, seed_value, current_time)


def _validate_task_id(task_id: str) -> None:
    """验证任务ID格式"""
    if not task_id or len(task_id.strip()) < 4:
        raise HTTPException(status_code=400, detail="无效的任务ID格式")


def _calculate_runtime_seconds(task_info: TaskInfo) -> Optional[int]:
    """计算任务运行时间"""
    if task_info.status != TaskStatus.RUNNING:
        return None

    try:
        created_time = datetime.fromisoformat(
            task_info.created_at.replace("Z", "+00:00")
        )
        return int((datetime.now(timezone.utc) - created_time).total_seconds())
    except (ValueError, AttributeError) as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"无法计算运行时间: {e}")
        return None


def _create_success_response(
    task_info: TaskInfo, include_guidance: bool = True
) -> SuccessResponse:
    """创建成功响应"""
    current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    data = task_info.dict()

    if include_guidance:
        guidance = get_client_guidance()
        runtime_seconds = _calculate_runtime_seconds(task_info)
        polling_guidance = guidance.get_polling_guidance(
            task_info.status.value, runtime_seconds
        )
        data["_polling_guidance"] = polling_guidance

    return SuccessResponse(
        status=ResponseStatus.SUCCESS,
        message="任务状态查询成功",
        timestamp=current_time,
        data=data,
    )


def _handle_database_fallback(task_id: str, error: Exception) -> SuccessResponse:
    """处理数据库fallback"""
    fallback_config = get_fallback_config()
    if not fallback_config.database_fallback_enabled:
        raise error

    try:
        task_info = get_mock_task_status(task_id)
        current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        return SuccessResponse(
            status=ResponseStatus.SUCCESS,
            message="任务状态查询成功（fallback模式）",
            timestamp=current_time,
            data={
                **task_info.dict(),
                "_fallback_mode": True,
                "_fallback_reason": "数据库连接异常",
            },
        )
    except Exception as mock_e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Mock fallback失败: {mock_e}")
        raise error


@router.get("/{task_id}", response_model=SuccessResponse, summary="查询任务状态")
async def get_task_status(
    task_id: str, db: AsyncSession = Depends(get_db)
) -> SuccessResponse:
    """查询指定任务的当前状态 - 简化版本

    消除深层嵌套，遵循Linus 3层规则。
    """
    import logging

    logger = logging.getLogger(__name__)

    _validate_task_id(task_id)

    try:
        service = TaskStatusService(db)
        task_info = await service.get_task_status(task_id)

        if not task_info:
            raise HTTPException(status_code=404, detail="任务不存在或已被删除")

        return _create_success_response(task_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"任务状态查询失败 - task_id: {task_id}, error: {str(e)}")

        try:
            return _handle_database_fallback(task_id, e)
        except Exception as fallback_e:
            logger.error(f"Fallback处理失败: {fallback_e}")
            raise HTTPException(status_code=500, detail="服务暂时不可用，请稍后重试")


def _parse_and_validate_batch_ids(task_ids: str, limit: int) -> List[str]:
    """解析并验证批量任务ID"""
    if not task_ids:
        raise HTTPException(status_code=400, detail="必须提供至少一个任务ID")

    task_id_list = [tid.strip() for tid in task_ids.split(",") if tid.strip()]

    if not task_id_list:
        raise HTTPException(status_code=400, detail="任务ID列表为空")

    fallback_config = get_fallback_config()
    max_limit = min(limit, fallback_config.max_batch_size)

    if len(task_id_list) > max_limit:
        raise HTTPException(status_code=400, detail=f"一次最多查询{max_limit}个任务")

    return task_id_list


def _create_batch_success_response(
    results: Dict[str, Union[TaskInfo, Dict[str, str]]], task_id_list: List[str]
) -> SuccessResponse:
    """创建批量查询成功响应"""
    successful_results = sum(
        1 for result in results.values() if isinstance(result, TaskInfo)
    )
    error_results = len(results) - successful_results
    current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return SuccessResponse(
        status=ResponseStatus.SUCCESS,
        message=f"批量查询完成，成功{successful_results}个，失败{error_results}个",
        timestamp=current_time,
        data={
            "total_requested": len(task_id_list),
            "total_processed": len(results),
            "successful_count": successful_results,
            "error_count": error_results,
            "tasks": results,
            "_batch_optimization": True,
        },
    )


def _handle_batch_fallback(
    task_id_list: List[str], error: Exception
) -> SuccessResponse:
    """处理批量查询fallback"""
    fallback_config = get_fallback_config()
    if not fallback_config.database_fallback_enabled:
        raise error

    results: Dict[str, Union[TaskInfo, Dict[str, str]]] = {}
    for task_id in task_id_list:
        try:
            results[task_id] = get_mock_task_status(task_id)
        except Exception as mock_e:
            results[task_id] = {"error": str(mock_e)}

    current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return SuccessResponse(
        status=ResponseStatus.SUCCESS,
        message=f"批量查询完成（fallback模式），共{len(results)}个任务",
        timestamp=current_time,
        data={
            "total_requested": len(task_id_list),
            "total_found": len(results),
            "tasks": results,
            "_fallback_mode": True,
            "_fallback_reason": "数据库连接异常",
        },
    )


@router.get("/", response_model=SuccessResponse, summary="批量查询任务状态")
async def get_multiple_tasks_status(
    task_ids: str, limit: int = 10, db: AsyncSession = Depends(get_db)
) -> SuccessResponse:
    """批量查询多个任务状态 - 简化版本"""
    import logging

    logger = logging.getLogger(__name__)

    task_id_list = _parse_and_validate_batch_ids(task_ids, limit)

    try:
        service = TaskStatusService(db)
        results = await service.get_multiple_tasks_status(
            task_id_list, len(task_id_list)
        )
        return _create_batch_success_response(results, task_id_list)

    except Exception as e:
        logger.error(f"批量查询失败 - task_ids: {task_id_list}, error: {str(e)}")

        try:
            return _handle_batch_fallback(task_id_list, e)
        except Exception as batch_e:
            logger.error(f"批量fallback处理失败: {batch_e}")
            raise HTTPException(status_code=500, detail="批量查询服务暂时不可用，请稍后重试")
