"""
Reddit Signal Scanner - 错误处理器

PRD02-07要求：统一的异常处理和客户端指导
- 4个异常处理函数，一对一映射
- 统一的错误响应格式
- 详细的错误日志记录
- 客户端恢复指导

Linus设计哲学：
- "消除特殊情况"：所有处理器都有相同的函数签名和返回格式
- "数据结构优先"：简单的字典映射，避免复杂的策略模式
- "一个函数做一件事"：每个处理器职责单一明确
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from .exceptions import (
    BaseApplicationError,
    DatabaseError,
    RedditAPIError,
    TaskNotFoundError,
    ValidationError,
)
from .types import JsonValue

logger = logging.getLogger(__name__)


def create_error_response(
    request: Request,
    exc: BaseApplicationError,
    error_type: str,
    additional_data: Optional[dict[str, JsonValue]] = None,
) -> dict[str, JsonValue]:
    """
    创建统一的错误响应格式 - 消除响应格式的特殊情况

    统一响应结构：
    - status: 固定为"error"
    - error_type: 错误分类
    - message: 用户友好的错误信息
    - recovery_hint: 恢复指导
    - timestamp: 错误发生时间
    - request_id: 请求追踪ID
    - context: 额外的错误上下文
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])
    timestamp = datetime.now(timezone.utc).isoformat()

    response_data: dict[str, JsonValue] = {
        "status": "error",
        "error_type": error_type,
        "message": exc.detail,
        "recovery_hint": exc.recovery_hint,
        "timestamp": timestamp,
        "request_id": request_id,
        # Normalize Mapping to dict to satisfy JsonValue (which allows dict, not Mapping)
        "context": dict(exc.context)
        if isinstance(exc.context, dict)
        else dict(exc.context),
    }

    # 添加额外数据（如恢复策略结果）
    if additional_data:
        response_data.update(additional_data)

    return response_data


def handle_validation_error(request: Request, exc: ValidationError) -> JSONResponse:
    """
    处理输入验证错误

    记录：警告级别日志（用户输入问题）
    响应：400状态码 + 详细字段信息
    """
    logger.warning(
        f"Validation error - {exc.detail}",
        extra={
            "error_type": "validation_error",
            "field": exc.context.get("field"),
            "request_path": request.url.path,
            "request_method": request.method,
        },
    )

    response_data = create_error_response(request, exc, "validation_error")
    return JSONResponse(status_code=400, content=response_data)


def handle_task_not_found(request: Request, exc: TaskNotFoundError) -> JSONResponse:
    """
    处理任务不存在错误

    记录：信息级别日志（正常业务场景）
    响应：404状态码 + task_id信息
    """
    task_id = exc.context.get("task_id")
    logger.info(
        f"Task not found - {task_id}",
        extra={
            "error_type": "task_not_found",
            "task_id": task_id,
            "request_path": request.url.path,
        },
    )

    response_data = create_error_response(request, exc, "task_not_found")
    return JSONResponse(status_code=404, content=response_data)


def handle_reddit_api_error(request: Request, exc: RedditAPIError) -> JSONResponse:
    """
    处理Reddit API错误

    记录：错误级别日志（外部服务问题）
    响应：503状态码 + 恢复策略信息
    """
    reddit_status = exc.context.get("reddit_status_code")
    logger.error(
        f"Reddit API error - {exc.detail}",
        extra={
            "error_type": "reddit_api_error",
            "reddit_status_code": reddit_status,
            "request_path": request.url.path,
            "recovery_strategy": "cache_fallback",
        },
    )

    # Reddit API错误需要触发恢复策略
    additional_data: dict[str, JsonValue] = {
        "recovery_strategy": "cache_fallback",
        "fallback_enabled": True,
        "cache_ttl": 300,  # 5分钟缓存
    }

    response_data = create_error_response(
        request, exc, "reddit_api_error", additional_data
    )
    return JSONResponse(status_code=503, content=response_data)


def handle_database_error(request: Request, exc: DatabaseError) -> JSONResponse:
    """
    处理数据库错误

    记录：严重级别日志（系统核心问题）
    响应：500状态码 + 重试机制信息
    """
    operation = exc.context.get("operation")
    logger.critical(
        f"Database error - {exc.detail}",
        extra={
            "error_type": "database_error",
            "operation": operation,
            "request_path": request.url.path,
            "recovery_strategy": "auto_retry",
        },
    )

    # 数据库错误需要触发重试机制
    additional_data: dict[str, JsonValue] = {
        "recovery_strategy": "auto_retry",
        "max_retries": 3,
        "retry_delay": 2,
        "auto_recovery": True,
    }

    response_data = create_error_response(
        request, exc, "database_error", additional_data
    )
    return JSONResponse(status_code=500, content=response_data)


def handle_generic_error(request: Request, exc: Exception) -> JSONResponse:
    """
    处理未预期异常的通用处理器

    记录：严重级别日志（系统未知问题）
    响应：500状态码 + 通用错误信息
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])

    logger.critical(
        f"Unhandled exception - {str(exc)}",
        exc_info=True,
        extra={
            "error_type": "internal_error",
            "request_path": request.url.path,
            "request_method": request.method,
            "request_id": request_id,
        },
    )

    response_data: dict[str, JsonValue] = {
        "status": "error",
        "error_type": "internal_error",
        "message": "服务内部错误，请稍后重试",
        "recovery_hint": "系统正在处理中，请稍后重试",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "context": {},
    }

    return JSONResponse(status_code=500, content=response_data)


# 错误处理器映射表 - Linus: "简单的数据结构胜过复杂的逻辑"
from typing import Callable as _Callable
from typing import Type as _Type
from typing import Callable as __Callable

ERROR_HANDLERS: Dict[_Type[BaseApplicationError], __Callable[..., JSONResponse]] = {
    ValidationError: handle_validation_error,
    TaskNotFoundError: handle_task_not_found,
    RedditAPIError: handle_reddit_api_error,
    DatabaseError: handle_database_error,
}
