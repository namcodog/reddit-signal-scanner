"""
Reddit Signal Scanner - 全局错误处理中间件

PRD02-07要求：全局异常处理器，统一的错误处理入口
- 拦截所有HTTP请求的异常
- 自动路由到对应的错误处理器
- 集成恢复策略，实现自动恢复
- 完整的错误日志和监控

Linus设计哲学：
- "在一个地方处理所有错误"：统一异常拦截点
- "消除特殊情况"：所有异常都经过相同的处理流程
- "实用主义"：专注解决真实的生产问题
"""

import asyncio
import logging
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional, Type

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.error_handlers import ERROR_HANDLERS, handle_generic_error
from app.schemas.responses.error import ErrorStatisticsResponse
from ..core.exceptions import BaseApplicationError, DatabaseError, RedditAPIError
from ..core.recovery import execute_recovery_strategy

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    全局错误处理中间件

    职责：
    1. 拦截所有HTTP请求异常
    2. 路由到对应的错误处理器
    3. 触发自动恢复策略
    4. 记录详细的错误指标
    """

    def __init__(self, app: Any, enable_recovery: bool = True) -> None:
        super().__init__(app)
        self.enable_recovery = enable_recovery
        self.error_counts: Dict[str, int] = {}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        中间件主要逻辑 - 异常拦截和处理分发

        处理流程：
        1. 生成请求追踪ID
        2. 记录请求开始时间
        3. 执行业务逻辑
        4. 如果异常，路由到错误处理器
        5. 记录请求指标和错误统计
        """
        # 生成请求追踪ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        start_time = time.time()

        try:
            # 执行正常的业务逻辑
            response = await call_next(request)

            # 记录成功请求的指标
            duration = time.time() - start_time
            self._log_request_metrics(
                request, response.status_code, duration, request_id
            )

            return response

        except Exception as exc:
            # 异常处理入口 - 统一处理所有异常
            duration = time.time() - start_time

            # 更新错误统计
            error_type = type(exc).__name__
            self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1

            # 路由到对应的错误处理器
            response = await self._handle_exception(request, exc, request_id)

            # 记录错误请求的指标
            self._log_error_metrics(request, exc, duration, request_id)

            return response

    async def _handle_exception(
        self, request: Request, exc: Exception, request_id: str
    ) -> JSONResponse:
        """
        异常处理分发器 - 根据异常类型路由到对应处理器

        处理优先级：
        1. 业务异常：使用专门的处理器
        2. 通用异常：使用通用处理器
        3. 自动恢复：在需要时触发恢复策略
        """

        # Constrain key type to BaseApplicationError subclasses
        exc_type: Type[BaseApplicationError] | None = (
            type(exc) if isinstance(exc, BaseApplicationError) else None
        )
        handler = ERROR_HANDLERS.get(exc_type) if exc_type else None

        if handler and isinstance(exc, BaseApplicationError):
            # 业务异常：使用专门处理器
            response = handler(request, exc)

            # 检查是否需要自动恢复
            if self.enable_recovery:
                recovery_result = await self._attempt_auto_recovery(request, exc)

                # 如果恢复成功，更新响应内容
                if recovery_result and recovery_result.success:
                    raw_body = getattr(response, "body", b"{}")
                    content = (
                        raw_body.decode()
                        if isinstance(raw_body, (bytes, bytearray))
                        else "{}"
                    )
                    import json

                    try:
                        content_dict = json.loads(content) if content else {}
                        content_dict["recovery"] = recovery_result.to_dict()
                        response = JSONResponse(
                            status_code=response.status_code, content=content_dict
                        )
                    except json.JSONDecodeError:
                        # JSON解析失败，保持原响应，但记录上下文
                        logger.debug("恢复信息合并时JSON解析失败，保持原响应", extra={"request_id": request_id})

            return response

        else:
            # 通用异常：使用通用处理器
            return handle_generic_error(request, exc)

    async def _attempt_auto_recovery(
        self, request: Request, exc: BaseApplicationError
    ) -> Optional[Any]:
        """
        尝试自动恢复 - 根据异常类型触发相应的恢复策略

        恢复策略映射：
        - RedditAPIError → cache_fallback
        - DatabaseError → retry_with_backoff
        - 其他异常 → 无自动恢复
        """

        if isinstance(exc, RedditAPIError):
            # Reddit API错误 → 缓存回退
            task_id = self._extract_task_id_from_request(request)
            error_context = {
                "reddit_status_code": exc.context.get("reddit_status_code"),
                "error_detail": exc.detail,
            }

            return await execute_recovery_strategy(
                "cache_fallback",
                task_id=task_id or "unknown",
                error_context=error_context,
            )

        elif isinstance(exc, DatabaseError):
            # 数据库错误 → 重试机制
            error_context = {
                "operation": exc.context.get("operation"),
                "error_detail": exc.detail,
            }

            # 注意：这里不能直接重试原操作，因为我们在中间件层
            # 只能返回重试策略的配置信息
            return await execute_recovery_strategy(
                "retry_with_backoff",
                operation=None,  # 无法在中间件层重试具体操作
                error_context=error_context,
            )

        # 其他异常暂不支持自动恢复
        return None

    def _extract_task_id_from_request(self, request: Request) -> Optional[str]:
        """
        从请求中提取task_id - 用于恢复策略

        提取优先级：
        1. URL路径参数
        2. 查询参数
        3. 请求体（JSON）
        """

        # 从URL路径提取 (如 /api/v1/tasks/abc123/status)
        path_segments = request.url.path.strip("/").split("/")
        if "tasks" in path_segments:
            try:
                task_index = path_segments.index("tasks")
                if task_index + 1 < len(path_segments):
                    return path_segments[task_index + 1]
            except (ValueError, IndexError):
                logger.debug(
                    "从URL路径提取 task_id 失败，忽略并继续",
                    extra={"path": request.url.path},
                )

        # 从查询参数提取
        task_id: Optional[str] = request.query_params.get("task_id")
        if task_id:
            return task_id

        # 从请求状态提取（如果业务逻辑已设置）
        if hasattr(request.state, "task_id"):
            try:
                task_id_attr = getattr(request.state, "task_id")
                return str(task_id_attr) if task_id_attr is not None else None
            except (AttributeError, ValueError, TypeError) as attr_err:
                logger.debug(
                    "读取 request.state.task_id 失败，返回 None",
                    extra={"error": str(attr_err)},
                )
                return None

        return None

    def _log_request_metrics(
        self, request: Request, status_code: int, duration: float, request_id: str
    ) -> None:
        """记录请求成功的指标"""

        log_level = logging.INFO
        if duration > 3.0:  # 超过3秒的慢请求
            log_level = logging.WARNING

        logger.log(
            log_level,
            f"Request completed - {request.method} {request.url.path} [{status_code}] {duration:.3f}s",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration": duration,
                "client_ip": request.client.host if request.client else "unknown",
            },
        )

    def _log_error_metrics(
        self, request: Request, exc: Exception, duration: float, request_id: str
    ) -> None:
        """记录错误请求的指标"""

        error_type = type(exc).__name__

        logger.error(
            f"Request failed - {request.method} {request.url.path} [{error_type}] {duration:.3f}s",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "error_type": error_type,
                "error_message": str(exc),
                "duration": duration,
                "client_ip": request.client.host if request.client else "unknown",
                "error_count": self.error_counts.get(error_type, 0),
            },
            exc_info=not isinstance(exc, BaseApplicationError),  # 业务异常不需要堆栈信息
        )

    def get_error_statistics(self) -> ErrorStatisticsResponse:
        """
        获取错误统计信息 - 用于监控和告警

        Returns:
            类型安全的错误统计响应模型
        """
        # type checked via import at module top
        total_errors = sum(self.error_counts.values())
        error_breakdown = dict(self.error_counts)
        most_common_error = (
            max(self.error_counts.items(), key=lambda x: x[1])[0]
            if self.error_counts
            else None
        )

        return ErrorStatisticsResponse(
            total_errors=total_errors,
            total_count=total_errors,  # 继承自BaseStatisticsResponse
            error_breakdown=error_breakdown,
            most_common_error=most_common_error,
            error_rate=None,  # 可以后续计算错误率
        )
