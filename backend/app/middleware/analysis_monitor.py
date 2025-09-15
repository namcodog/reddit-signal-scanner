"""
分析引擎监控中间件 - FastAPI请求级监控

设计原则：
1. 透明监控 - 不影响业务逻辑
2. 性能优先 - 最小开销
3. 统一接口 - 复用现有监控框架
"""

import time
import logging
import uuid
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional, Mapping, cast

from fastapi import Request, Response
from app.core.types import TypedRedis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.analyzer_metrics import (
    AnalysisMetricsCollector,
    AnalysisStep,
    get_metrics_collector,
)
from app.core.redis_client import get_redis_client
from app.services.alert_processor import AlertProcessor
from app.core.config import get_settings
from app.core.types import RedisValue


class AnalysisMonitoringMiddleware(BaseHTTPMiddleware):
    """
    分析引擎监控中间件

    监控范围：
    1. /api/v1/analysis/* 端点性能
    2. 缓存命中率实时统计
    3. API调用频率和限制
    4. 5分钟SLA跟踪
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.collector = get_metrics_collector()
        self._redis: Optional[TypedRedis] = None
        self.alert_processor: Any = AlertProcessor()

        # 监控配置
        self.sla_threshold = 300  # 5分钟
        self.cache_threshold = 0.6  # 60%命中率

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """处理请求并收集指标"""

        # 只监控分析相关端点
        settings = get_settings()
        if not request.url.path.startswith(f"{settings.api_prefix}/analysis"):
            return await call_next(request)

        # 生成分析ID
        analysis_id = request.headers.get("X-Analysis-ID", str(uuid.uuid4()))
        request.state.analysis_id = analysis_id

        # 开始计时
        start_time = time.time()

        # 提取关键字（如果有）
        keyword = ""
        if request.method == "POST":
            try:
                body = await request.body()
                import json

                data = json.loads(body)
                keyword = data.get("keyword", "")
                # 重建request以便后续处理
                from starlette.requests import Request as StarletteRequest

                scope = request.scope
                scope["body"] = body
                request = StarletteRequest(scope, receive=request.receive)
                request._body = body
                request.state.analysis_id = analysis_id
            except json.JSONDecodeError:
                # 非JSON请求体，忽略关键字提取
                keyword = ""
            except Exception as parse_error:
                # 保守降级：不阻断主流程，但记录上下文
                try:
                    from app.core.monitoring import send_alert, AlertLevel

                    await self._await_maybe(send_alert(
                        AlertLevel.WARNING,
                        "analysis_monitor",
                        "请求体解析失败，已降级继续",
                        {"error": str(parse_error)},
                    ))
                except Exception as send_err:
                    # 监控发送失败不阻断，但记录上下文
                    logging.getLogger(__name__).warning(
                        "监控发送失败，已忽略", extra={"error": str(send_err)}
                    )

        # 初始化分析监控
        if keyword:
            self.collector.start_analysis(analysis_id, keyword)

        try:
            # 执行请求
            response = await call_next(request)

            # 记录成功指标
            execution_time = time.time() - start_time
            await self._record_success_metrics(
                analysis_id, request.url.path, execution_time, response.status_code
            )

            # 检查SLA
            if execution_time > self.sla_threshold:
                await self._trigger_sla_alert(analysis_id, execution_time)

            # 添加性能头
            response.headers["X-Analysis-ID"] = analysis_id
            response.headers["X-Execution-Time"] = f"{execution_time:.3f}"

            return response

        except Exception as e:
            # 记录失败指标
            execution_time = time.time() - start_time
            await self._record_error_metrics(
                analysis_id, request.url.path, execution_time, str(e)
            )
            raise

        finally:
            # 完成分析监控
            if self.collector.current_analysis:
                metrics = self.collector.complete_analysis()
                if metrics:
                    await self._save_metrics(metrics)

    async def _get_redis(self) -> TypedRedis:
        """懒加载获取底层Redis客户端，并缓存。"""
        if self._redis is None:
            rc = await get_redis_client()
            if rc.client is None:
                await rc.connect()
            self._redis = rc.client
        assert self._redis is not None
        return self._redis

    async def _await_maybe(self, value: Any) -> Any:
        """如果值可等待则等待，否则直接返回（兼容不同redis异步签名）。"""
        try:
            getattr(value, "__await__")
        except Exception:
            return value
        else:
            return await value

    async def _record_success_metrics(
        self, analysis_id: str, path: str, execution_time: float, status_code: int
    ) -> None:
        """记录成功请求的指标"""

        # 确定分析步骤
        step = self._path_to_step(path)
        if not step:
            return

        # 更新Redis中的实时指标
        metrics_key = f"analysis:metrics:{analysis_id}"
        client = await self._get_redis()
        await self._await_maybe(client.hset(
            metrics_key,
            mapping={
                "path": path,
                "execution_time": str(execution_time),
                "status_code": str(status_code),
                "timestamp": datetime.utcnow().isoformat(),
            },
        ))
        await self._await_maybe(client.expire(metrics_key, 3600))  # 1小时过期

        # 更新步骤统计
        stats_key = f"analysis:stats:{step.value}"
        await self._await_maybe(client.hincrby(stats_key, "total_requests", 1))
        await self._await_maybe(client.hincrbyfloat(stats_key, "total_time", execution_time))

        # 滑动窗口统计（用于实时监控）
        window_key = f"analysis:window:{step.value}:{int(time.time() // 60)}"
        await self._await_maybe(client.incr(window_key))
        await self._await_maybe(client.expire(window_key, 300))  # 5分钟窗口

    async def _record_error_metrics(
        self, analysis_id: str, path: str, execution_time: float, error: str
    ) -> None:
        """记录错误请求的指标"""

        step = self._path_to_step(path)
        if not step:
            return

        # 记录错误
        error_key = f"analysis:errors:{analysis_id}"
        client = await self._get_redis()
        await self._await_maybe(client.hset(
            error_key,
            mapping={
                "path": path,
                "execution_time": str(execution_time),
                "error": error,
                "timestamp": datetime.utcnow().isoformat(),
            },
        ))
        await self._await_maybe(client.expire(error_key, 86400))  # 24小时

        # 更新错误统计
        stats_key = f"analysis:stats:{step.value}"
        await self._await_maybe(client.hincrby(stats_key, "total_errors", 1))

    async def _save_metrics(self, metrics: Any) -> None:
        """保存完整的分析指标"""

        # 保存到Redis（热数据）
        metrics_json = metrics.json()
        client = await self._get_redis()
        await self._await_maybe(client.setex(
            f"analysis:complete:{metrics.analysis_id}", 3600, metrics_json  # 1小时
        ))

        # 检查缓存健康度
        if not metrics.is_cache_healthy:
            await self._trigger_cache_alert(
                metrics.analysis_id, metrics.cache_hit_rate_overall
            )

        # TODO: 异步保存到PostgreSQL（冷数据）

    async def _trigger_sla_alert(self, analysis_id: str, execution_time: float) -> None:
        """触发SLA超时告警"""
        alert_data = {
            "alert_type": "sla_timeout",
            "analysis_id": analysis_id,
            "execution_time": execution_time,
            "threshold": self.sla_threshold,
            "severity": "critical",
            "message": f"分析执行时间 {execution_time:.1f}秒 超过5分钟SLA",
        }

        await self.alert_processor.process_alert(alert_data)

    async def _trigger_cache_alert(self, analysis_id: str, hit_rate: float) -> None:
        """触发缓存命中率告警"""
        alert_data = {
            "alert_type": "cache_hit_low",
            "analysis_id": analysis_id,
            "cache_hit_rate": hit_rate,
            "threshold": self.cache_threshold * 100,
            "severity": "warning",
            "message": f"缓存命中率 {hit_rate:.1f}% 低于60%阈值",
        }

        await self.alert_processor.process_alert(alert_data)

    def _path_to_step(self, path: str) -> Optional[AnalysisStep]:
        """将API路径映射到分析步骤"""
        settings = get_settings()
        prefix = settings.api_prefix
        mapping = {
            f"{prefix}/analysis/discover": AnalysisStep.STEP1_COMMUNITY,
            f"{prefix}/analysis/collect": AnalysisStep.STEP2_REDDIT_DATA,
            f"{prefix}/analysis/extract": AnalysisStep.STEP3_AI_EXTRACTION,
            f"{prefix}/analysis/rank": AnalysisStep.STEP4_RANKING,
            f"{prefix}/analysis/cache": AnalysisStep.CACHE_MAINTENANCE,
        }

        for pattern, step in mapping.items():
            if pattern in path:
                return step

        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    API限流中间件 - 保护Reddit API配额
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._redis: Optional[TypedRedis] = None
        self.rate_limits = {
            "reddit": (1000, 600),  # 1000请求/10分钟
            "openai": (500, 60),  # 500请求/分钟
        }

    # _get_redis 定义见类尾部，避免重复定义

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """检查和执行限流"""

        # 识别API类型
        api_type = self._identify_api_type(request.url.path)
        if not api_type:
            return await call_next(request)

        # 检查限流
        limit, window = self.rate_limits.get(api_type, (1000, 60))
        key = f"ratelimit:{api_type}:{int(time.time() // window)}"

        client = await self._get_redis()
        current = await client.incr(key)
        if current == 1:
            await client.expire(key, window)

        # 检查是否超限
        remaining = limit - current
        if remaining < 0:
            response = Response(
                content="Rate limit exceeded",
                status_code=429,
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + window),
                },
            )
            return response

        # 执行请求
        response = await call_next(request)

        # 添加限流头
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + window)

        # 预警检查
        if remaining < limit * 0.2:  # 剩余20%时预警
            await self._trigger_rate_limit_warning(api_type, remaining, limit)

        return response

    def _identify_api_type(self, path: str) -> Optional[str]:
        """识别API类型"""
        if "reddit" in path or "/r/" in path:
            return "reddit"
        elif "openai" in path or "gpt" in path:
            return "openai"
        return None

    async def _get_redis(self) -> TypedRedis:
        """懒加载获取底层Redis客户端，并缓存。"""
        if self._redis is None:
            rc = await get_redis_client()
            if rc.client is None:
                await rc.connect()
            self._redis = rc.client
        assert self._redis is not None
        return self._redis

    async def _trigger_rate_limit_warning(
        self, api_type: str, remaining: int, limit: int
    ) -> None:
        """触发限流预警"""
        usage_percent = ((limit - remaining) / limit) * 100
        if usage_percent > 80:  # 使用超过80%
            alert_processor: Any = AlertProcessor()
            await alert_processor.process_alert(
                {
                    "alert_type": "rate_limit_warning",
                    "api_type": api_type,
                    "remaining": remaining,
                    "limit": limit,
                    "usage_percent": usage_percent,
                    "severity": "warning",
                    "message": f"{api_type} API使用率 {usage_percent:.1f}%，剩余配额: {remaining}",
                }
            )
