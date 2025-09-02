"""
性能监控中间件 - Reddit Signal Scanner
实现PRD02-08要求的API响应时间监控和性能指标收集

基于Linus原则：
- 简洁胜过聪明：50行代码解决问题
- 数据结构优先：复用现有monitoring.py的完整体系
- Never break userspace：零破坏性，纯监控功能
"""

import time
import logging
import re
from typing import Callable, Any
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware

from ..core.monitoring import record_metric, MetricType

logger = logging.getLogger(__name__)


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    API性能监控中间件

    功能：
    - 自动监控所有API端点响应时间
    - 集成现有monitoring.py告警系统
    - 支持PRD02-08的SLA目标检查
    """

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self.monitored_endpoints = {
            # PRD02-08要求的关键端点
            "POST:/api/analyze",
            "GET:/api/status",
            "GET:/api/report",
            # 可扩展的其他端点
            "GET:/api/health",
            "GET:/metrics",
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录性能指标"""

        # 记录开始时间 - 使用高精度性能计数器
        start_time = time.perf_counter()

        # 构建标准化路由标识 - 防止动态参数导致标签爆炸
        route_key = self._normalize_route(str(request.url.path), request.method)

        try:
            # 执行请求
            response = await call_next(request)

            # 计算响应时间
            duration = time.perf_counter() - start_time

            # 记录性能指标 - 集成现有monitoring系统
            self._record_performance_metrics(route_key, duration, response.status_code)

            # 添加性能调试头（开发环境）
            response.headers["X-Response-Time"] = f"{duration:.3f}"
            response.headers["X-Monitored"] = "true"

            return response

        except Exception as e:
            # 记录错误响应时间
            duration = time.perf_counter() - start_time
            self._record_error_metrics(route_key, duration, str(e))

            # 重新抛出异常，保持错误处理链完整
            raise

    def _normalize_route(self, path: str, method: str) -> str:
        """
        标准化路由，避免动态参数导致标签爆炸
        将 /api/report/123 标准化为 /api/report/{id}
        """
        # 数字ID参数标准化 (/api/report/123 -> /api/report/{id})
        normalized = re.sub(r"/\d+", "/{id}", path)

        # UUID参数标准化 (/api/user/a1b2c3d4-... -> /api/user/{uuid})
        normalized = re.sub(r"/[a-f0-9-]{36}", "/{uuid}", normalized)

        # 其他常见模式...
        # normalized = re.sub(r'/[a-zA-Z0-9_-]{20,}', '/{token}', normalized)

        return f"{method}:{normalized}"

    def _record_performance_metrics(
        self, route: str, duration: float, status_code: int
    ) -> None:
        """记录性能指标到现有监控系统"""
        try:
            # 响应时间指标 - 触发monitoring.py第300-327行告警规则
            record_metric(
                name="response_time",
                value=duration,
                metric_type=MetricType.TIMER,
                labels={"route": route, "status": str(status_code)},
            )

            # 请求成功计数器
            record_metric(
                name="api_requests_total",
                value=1,
                metric_type=MetricType.COUNTER,
                labels={
                    "route": route,
                    "status": "success" if 200 <= status_code < 400 else "error",
                },
            )

            logger.debug(f"性能指标记录: {route} {duration:.3f}s [{status_code}]")

        except Exception as e:
            # 监控系统本身不应影响业务
            logger.warning(f"性能指标记录失败: {e}")

    def _record_error_metrics(self, route: str, duration: float, error: str) -> None:
        """记录错误指标"""
        try:
            # 错误响应时间
            record_metric(
                name="response_time",
                value=duration,
                metric_type=MetricType.TIMER,
                labels={"route": route, "status": "500", "error": "true"},
            )

            # 错误计数器
            record_metric(
                name="api_errors_total",
                value=1,
                metric_type=MetricType.COUNTER,
                labels={"route": route},
            )

            logger.error(f"API错误记录: {route} {duration:.3f}s - {error}")

        except Exception as e:
            logger.warning(f"错误指标记录失败: {e}")


# Linus风格：简单胜过聪明的性能监控工具
from contextlib import contextmanager


@contextmanager
def monitor_execution(metric_name: str):
    """
    性能监控上下文管理器 - Linus风格的简洁实现

    用法:
        with monitor_execution("database_query"):
            result = await db.query()

    Args:
        metric_name: 指标名称
    """
    start = time.perf_counter()
    try:
        yield
    except Exception:
        # 记录错误执行时间
        duration = time.perf_counter() - start
        record_metric(f"{metric_name}_error", duration, MetricType.TIMER)
        raise
    else:
        # 记录成功执行时间
        duration = time.perf_counter() - start
        record_metric(metric_name, duration, MetricType.TIMER)


# 导出接口
__all__ = ["PerformanceMiddleware", "monitor_execution"]
