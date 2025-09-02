"""
Reddit Signal Scanner - 分析任务端点

PRD02-02 + PRD04-02集成实现：
- 实现POST /api/analyze端点，输入验证和异步任务创建
- 集成Celery任务生产者，支持异步处理
- 响应时间优化：<200ms目标
- 错误处理：400 Bad Request, 422 Validation Error
"""

import time
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from ...api.models import SuccessResponse, ResponseStatus
from ...schemas.task import AnalyzeRequest, AnalyzeResponse, TaskInfo, TaskStatus
from ...schemas.task_producer import TaskSubmissionRequest
from ...core.validation import ContentValidator
from ...core.database import get_db
from ...core.task_manager import get_task_manager, TaskManager
from ...core.user_context import (
    get_anonymous_user_context,
    UserContext,
)  # 新增：用户上下文导入
from ...models.task import Task as TaskModel

router = APIRouter(prefix="/analyze", tags=["分析任务"])


@router.post("/", response_model=AnalyzeResponse, summary="创建分析任务")
async def create_analysis_task(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    task_manager: TaskManager = Depends(get_task_manager),  # 任务管理器依赖
    user_context: UserContext = Depends(
        get_anonymous_user_context
    ),  # 新增：用户上下文依赖
) -> AnalyzeResponse:
    """
    创建Reddit信号分析任务 - PRD02-02 + PRD04-02集成实现

    集成了同步和异步两种处理模式：
    1. 输入验证：10-2000字符限制，恶意输入过滤 (PRD02-02)
    2. 任务创建：生成UUID，写入数据库 (PRD02-02)
    3. 异步任务提交：Celery任务队列处理 (PRD04-02 NEW!)
    4. 快速响应：返回task_id和队列状态 (PRD04-02 NEW!)
    5. 错误处理：400 Bad Request, 422 Validation Error
    6. 响应时间：<200ms优化目标
    7. 用户身份管理：安全的用户上下文 (安全修复)

    新增功能（PRD04-02）：
    - 集成TaskManager和TaskProducer
    - Celery异步任务提交
    - 队列状态和预估时间
    - 统一的任务生命周期管理
    - 用户身份管理和权限控制

    Returns:
        任务创建成功响应，包含task_id、队列状态和预估信息

    Raises:
        HTTPException: 400 - 输入验证失败
        HTTPException: 422 - Pydantic验证失败（自动处理）
        HTTPException: 500 - 数据库操作或任务提交失败
    """

    # Linus修复：从TaskConfig获取配置参数
    from ...schemas.task_producer import TaskConfig

    config = TaskConfig.default_config()

    # 开始计时，监控响应时间
    start_time = time.time()

    try:
        # 第1步：内容安全验证（PRD02-02保持不变）
        validated_description = ContentValidator.validate_product_description(
            request.product_description
        )

        # 第2步：创建任务提交请求（PRD04-02新增）
        task_submission = TaskSubmissionRequest(
            product_description=validated_description,
            priority=1,  # 默认优先级
            metadata={
                "api_version": "v1",
                "source": "web_api",
                "user_type": (
                    "system"
                    if user_context.is_system_user
                    else "anonymous" if user_context.is_anonymous else "authenticated"
                ),
            },
        )

        # 第3步：通过TaskManager提交异步任务（PRD04-02核心功能，传递用户上下文）
        task_response = await task_manager.create_task(
            task_submission, db, user_context
        )

        # 第4步：构造统一响应（兼容PRD02-02格式，扩展PRD04-02信息）
        current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # 构造TaskInfo（兼容现有API模型）
        task_info = TaskInfo(
            task_id=task_response.task_id,
            status=TaskStatus.QUEUED,  # 新状态：已入队等待处理
            progress=0,
            created_at=task_response.submitted_at.isoformat().replace("+00:00", "Z"),
            updated_at=task_response.submitted_at.isoformat().replace("+00:00", "Z"),
            estimated_completion=(
                task_response.estimated_start_time.isoformat().replace("+00:00", "Z")
                if task_response.estimated_start_time
                else None
            ),
            error_message=None,
        )

        # 第5步：性能监控（PRD02-02保持）- Linus修复：配置化阈值
        elapsed_time = (time.time() - start_time) * 1000  # 转换为毫秒
        if elapsed_time > config.api_response_time_threshold_ms:  # 使用配置化的阈值
            # TODO: 发送性能告警
            logger.warning(
                f"API响应时间超过阈值: {elapsed_time:.2f}ms > {config.api_response_time_threshold_ms}ms"
            )
            pass

        # 构造增强响应消息
        response_message = (
            f"分析任务已创建并提交到队列，产品描述: '{validated_description[:50]}...'"
            f" | 队列: {task_response.queue_name}"
            f" | 预估开始: {task_response.estimated_start_time.strftime('%H:%M:%S') if task_response.estimated_start_time else '立即'}"
            f" | 用户: {user_context}"
        )

        return AnalyzeResponse(
            status=ResponseStatus.SUCCESS,
            message=response_message,
            timestamp=current_time,
            data=task_info,
        )

    except ValueError as e:
        # 输入验证失败 (PRD02-02)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"输入验证失败: {str(e)}"
        )
    except SQLAlchemyError as e:
        # 数据库操作失败 (PRD02-02)
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"数据库操作失败: {e}", exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="数据库操作失败，请重试",
        )
    except Exception as e:
        # 任务提交失败或其他未预期错误 (PRD04-02新增处理)
        # 记录详细错误信息用于调试
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"任务创建失败: {e}", exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="任务创建失败，请稍后重试",
        )


@router.get("/{task_id}/cancel", response_model=SuccessResponse, summary="取消分析任务")
async def cancel_analysis_task(task_id: str) -> SuccessResponse:
    """
    取消正在运行的分析任务

    当前状态：空实现
    TODO: prd02-03实现任务取消逻辑
    """

    current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return SuccessResponse(
        status=ResponseStatus.SUCCESS,
        message=f"任务 {task_id} 取消请求已提交",
        timestamp=current_time,
        data={"task_id": task_id, "action": "cancel_requested"},
    )
