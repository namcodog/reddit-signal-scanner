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
from typing import Dict, Any, Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.exceptions import BaseApplicationError, RedditAPIError, DatabaseError
from ..core.error_handlers import ERROR_HANDLERS, handle_generic_error
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

    def __init__(self, app, enable_recovery: bool = True):
        super().__init__(app)
        self.enable_recovery = enable_recovery
        self.error_counts: Dict[str, int] = {}

    async def dispatch(self, request: Request, call_next) -> Response:
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

        # 查找专门的错误处理器
        handler = ERROR_HANDLERS.get(type(exc))

        if handler and isinstance(exc, BaseApplicationError):
            # 业务异常：使用专门处理器
            response = handler(request, exc)

            # 检查是否需要自动恢复
            if self.enable_recovery:
                recovery_result = await self._attempt_auto_recovery(request, exc)

                # 如果恢复成功，更新响应内容
                if recovery_result and recovery_result.success:
                    content = (
                        response.body.decode() if hasattr(response, "body") else "{}"
                    )
                    import json

                    try:
                        content_dict = json.loads(content) if content else {}
                        content_dict["recovery"] = recovery_result.to_dict()
                        response = JSONResponse(
                            status_code=response.status_code, content=content_dict
                        )
                    except json.JSONDecodeError:
                        # JSON解析失败，保持原响应
                        pass

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
                pass

        # 从查询参数提取
        task_id = request.query_params.get("task_id")
        if task_id:
            return task_id

        # 从请求状态提取（如果业务逻辑已设置）
        if hasattr(request.state, "task_id"):
            return request.state.task_id

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
            exc_info=not isinstance(
                exc, BaseApplicationError
            ),  # 业务异常不需要堆栈信息
        )

    def get_error_statistics(self) -> Dict[str, Any]:
        """
        获取错误统计信息 - 用于监控和告警

        Returns:
            包含错误类型统计的字典
        """

        total_errors = sum(self.error_counts.values())

        return {
            "total_errors": total_errors,
            "error_breakdown": dict(self.error_counts),
            "most_common_error": (
                max(self.error_counts.items(), key=lambda x: x[1])[0]
                if self.error_counts
                else None
            ),
        }
