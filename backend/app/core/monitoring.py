"""
监控告警系统 - Reddit Signal Scanner
为数据清理服务提供完整的监控和告警机制

基于Linus生产部署要求：
- 实时性能监控
- 异常自动告警
- 健康检查端点
- 指标收集和上报
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypedDict

from ..core.config import get_settings

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """告警级别枚举"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(Enum):
    """指标类型枚举"""

    COUNTER = "counter"  # 计数器
    GAUGE = "gauge"  # 瞬时值
    HISTOGRAM = "histogram"  # 直方图
    TIMER = "timer"  # 计时器


class AlertDetails(TypedDict, total=False):
    metric: str
    value: float
    timeout_count: int
    rate: float
    route: str
    duration_ms: float
    target_ms: float
    excess_factor: float
    table: str
    duration: float
    threshold: float
    category: str
    error: str


class RecentAlerts(TypedDict):
    critical: int
    error: int
    warning: int
    info: int


class HealthStatusSummary(TypedDict):
    status: str
    timestamp: str
    metrics_count: int
    active_alerts: int
    recent_alerts: RecentAlerts


class MetricSummary(TypedDict):
    count: int
    avg: float
    min: float
    max: float
    latest: float


MetricsSummary = Dict[str, MetricSummary]


@dataclass
class Alert:
    """告警数据结构"""

    alert_id: str
    level: AlertLevel
    service: str
    message: str
    details: AlertDetails
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class Metric:
    """监控指标数据结构"""

    name: str
    value: float
    type: MetricType
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MonitoringService:
    """
    监控服务 - 统一的监控和告警管理

    功能：
    - 指标收集和上报
    - 异常检测和告警
    - 健康检查
    - 性能监控
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.metrics: Dict[str, List[Metric]] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_handlers: List[Callable[[Alert], None]] = []
        self._setup_default_handlers()

    def _setup_default_handlers(self) -> None:
        """设置默认的告警处理器"""
        self.alert_handlers.append(self._log_alert)

        # 生产环境可以添加更多处理器
        # self.alert_handlers.append(self._send_email_alert)
        # self.alert_handlers.append(self._send_slack_alert)

    def record_metric(
        self,
        name: str,
        value: float,
        metric_type: MetricType,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """记录监控指标"""
        try:
            metric = Metric(
                name=name, value=value, type=metric_type, labels=labels or {}
            )

            if name not in self.metrics:
                self.metrics[name] = []

            self.metrics[name].append(metric)

            # 保持指标历史记录在合理范围内（最近1000个）
            if len(self.metrics[name]) > 1000:
                self.metrics[name] = self.metrics[name][-1000:]

            # 检查是否需要触发告警
            self._check_metric_alerts(metric)

        except Exception as e:
            logger.error(f"记录监控指标失败: {e}")

    def send_alert(
        self,
        level: AlertLevel,
        service: str,
        message: str,
        details: Optional[AlertDetails] = None,
    ) -> str:
        """发送告警"""
        try:
            alert_id = f"{service}_{int(time.time() * 1000)}"

            alert = Alert(
                alert_id=alert_id,
                level=level,
                service=service,
                message=message,
                details=details or {},
                timestamp=datetime.now(timezone.utc),
            )

            self.active_alerts[alert_id] = alert

            # 触发所有告警处理器
            for handler in self.alert_handlers:
                try:
                    handler(alert)
                except Exception as handler_error:
                    logger.error(f"告警处理器执行失败: {handler_error}")

            return alert_id

        except Exception as e:
            logger.error(f"发送告警失败: {e}")
            return ""

    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警"""
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.resolved = True
                alert.resolved_at = datetime.now(timezone.utc)

                logger.info(f"告警已解决: {alert_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"解决告警失败: {e}")
            return False

    def get_health_status(self) -> HealthStatusSummary:
        """获取系统健康状态"""
        try:
            now = datetime.now(timezone.utc)

            # 统计最近5分钟的告警
            recent_alerts = [
                alert
                for alert in self.active_alerts.values()
                if not alert.resolved and (now - alert.timestamp) < timedelta(minutes=5)
            ]

            # 统计告警级别
            critical_count = len(
                [a for a in recent_alerts if a.level == AlertLevel.CRITICAL]
            )
            error_count = len([a for a in recent_alerts if a.level == AlertLevel.ERROR])
            warning_count = len(
                [a for a in recent_alerts if a.level == AlertLevel.WARNING]
            )

            # 判断总体健康状态
            if critical_count > 0:
                status = "critical"
            elif error_count > 3:  # 超过3个错误级别告警
                status = "unhealthy"
            elif warning_count > 10:  # 超过10个警告级别告警
                status = "degraded"
            else:
                status = "healthy"

            return {
                "status": status,
                "timestamp": now.isoformat(),
                "metrics_count": sum(len(metrics) for metrics in self.metrics.values()),
                "active_alerts": len(
                    [a for a in self.active_alerts.values() if not a.resolved]
                ),
                "recent_alerts": {
                    "critical": critical_count,
                    "error": error_count,
                    "warning": warning_count,
                    "info": len(
                        [a for a in recent_alerts if a.level == AlertLevel.INFO]
                    ),
                },
            }

        except Exception as e:
            logger.error(f"获取健康状态失败: {e}")
            # 回退到最小可用健康摘要，避免类型不匹配
            return {
                "status": "unknown",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics_count": 0,
                "active_alerts": 0,
                "recent_alerts": {"critical": 0, "error": 0, "warning": 0, "info": 0},
            }

    def get_metrics_summary(self, hours: int = 1) -> MetricsSummary:
        """获取指标摘要"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            summary: MetricsSummary = {}

            for name, metrics in self.metrics.items():
                recent_metrics = [m for m in metrics if m.timestamp >= cutoff_time]

                if recent_metrics:
                    values = [m.value for m in recent_metrics]
                    summary[name] = {
                        "count": len(values),
                        "avg": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                        "latest": values[-1],
                    }

            return summary

        except Exception as e:
            logger.error(f"获取指标摘要失败: {e}")
            return {}

    def _check_metric_alerts(self, metric: Metric) -> None:
        """检查指标是否触发告警"""
        try:
            # 数据清理相关的告警规则
            if metric.name == "cleanup_records_cleaned":
                # 单次清理记录过多告警
                if metric.value > 100000:
                    self.send_alert(
                        AlertLevel.WARNING,
                        "data_cleanup",
                        f"单次清理记录数量异常: {metric.value} 条",
                        {"metric": metric.name, "value": metric.value},
                    )

            elif metric.name == "cleanup_execution_time":
                # 清理执行时间过长告警
                if metric.value > 3600:  # 超过1小时
                    self.send_alert(
                        AlertLevel.ERROR,
                        "data_cleanup",
                        f"清理执行时间过长: {metric.value} 秒",
                        {"metric": metric.name, "value": metric.value},
                    )

            elif metric.name == "cleanup_lock_timeout":
                # 锁超时告警
                if metric.value > 0:
                    self.send_alert(
                        AlertLevel.ERROR,
                        "cleanup_locks",
                        "清理锁获取超时",
                        {"metric": metric.name, "timeout_count": int(metric.value)},
                    )

            elif metric.name == "cleanup_failure_rate":
                # 清理失败率告警
                if metric.value > 0.1:  # 失败率超过10%
                    self.send_alert(
                        AlertLevel.CRITICAL,
                        "data_cleanup",
                        f"清理失败率异常: {metric.value * 100:.1f}%",
                        {"metric": metric.name, "rate": metric.value},
                    )

            # PRD02-08 响应时间监控告警规则
            elif metric.name == "response_time":
                route = metric.labels.get("route", "unknown")
                duration = metric.value

                # PRD要求的SLA检查
                sla_targets = {
                    "POST:/api/analyze": 0.2,  # 200ms
                    "GET:/api/status": 0.01,  # 10ms
                    "GET:/api/report": 0.02,  # 20ms
                }

                target_time = sla_targets.get(route)
                if target_time and duration > target_time:
                    # 超出目标时间告警
                    excess_factor = duration / target_time
                    level = (
                        AlertLevel.CRITICAL if excess_factor > 3 else AlertLevel.WARNING
                    )

                    self.send_alert(
                        level,
                        "api_performance",
                        f"API响应时间超标: {route} 耗时{duration*1000:.0f}ms (目标{target_time*1000:.0f}ms)",
                        {
                            "route": route,
                            "duration_ms": duration * 1000,
                            "target_ms": target_time * 1000,
                            "excess_factor": excess_factor,
                        },
                    )

            elif metric.name == "slow_query":
                # 慢查询告警
                query_time = metric.value
                table_name = metric.labels.get("table", "unknown")

                if query_time > 1.0:  # 超过1秒的查询
                    level = (
                        AlertLevel.CRITICAL if query_time > 5.0 else AlertLevel.WARNING
                    )
                    self.send_alert(
                        level,
                        "database_performance",
                        f"慢查询检测: {table_name}表查询耗时{query_time:.2f}秒",
                        {"table": table_name, "duration": query_time, "threshold": 1.0},
                    )

        except Exception as e:
            logger.error(f"检查指标告警失败: {e}")

    def _log_alert(self, alert: Alert) -> None:
        """日志告警处理器"""
        log_message = f"[{alert.level.value.upper()}] {alert.service}: {alert.message}"

        if alert.level == AlertLevel.CRITICAL:
            logger.critical(log_message, extra={"alert_details": alert.details})
        elif alert.level == AlertLevel.ERROR:
            logger.error(log_message, extra={"alert_details": alert.details})
        elif alert.level == AlertLevel.WARNING:
            logger.warning(log_message, extra={"alert_details": alert.details})
        else:
            logger.info(log_message, extra={"alert_details": alert.details})

    def cleanup_old_data(self, days: int = 7) -> None:
        """清理旧的监控数据"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)

            # 清理旧指标
            cleaned_metrics = 0
            for name in self.metrics:
                old_count = len(self.metrics[name])
                self.metrics[name] = [
                    m for m in self.metrics[name] if m.timestamp >= cutoff_time
                ]
                cleaned_metrics += old_count - len(self.metrics[name])

            # 清理已解决的旧告警
            old_alert_ids = [
                alert_id
                for alert_id, alert in self.active_alerts.items()
                if alert.resolved
                and alert.resolved_at
                and alert.resolved_at < cutoff_time
            ]

            for alert_id in old_alert_ids:
                del self.active_alerts[alert_id]

            logger.info(f"清理监控数据完成: {cleaned_metrics} 个指标, {len(old_alert_ids)} 个告警")

        except Exception as e:
            logger.error(f"清理监控数据失败: {e}")


# 全局监控服务实例
_monitoring_service = None


def get_monitoring_service() -> MonitoringService:
    """获取全局监控服务实例"""
    global _monitoring_service

    if _monitoring_service is None:
        _monitoring_service = MonitoringService()

    return _monitoring_service


# 便捷函数
def record_metric(
    name: str,
    value: float,
    metric_type: MetricType,
    labels: Optional[Dict[str, str]] = None,
) -> None:
    """记录指标的便捷函数"""
    service = get_monitoring_service()
    service.record_metric(name, value, metric_type, labels)


def send_alert(
    level: AlertLevel,
    service: str,
    message: str,
    details: Optional[AlertDetails] = None,
) -> str:
    """发送告警的便捷函数"""
    monitoring_service = get_monitoring_service()
    return monitoring_service.send_alert(level, service, message, details)


def get_health_status() -> HealthStatusSummary:
    """获取健康状态的便捷函数"""
    service = get_monitoring_service()
    return service.get_health_status()


# 监控装饰器
def monitor_execution_time(metric_name: str) -> Callable[..., Any]:
    """监控函数执行时间的装饰器"""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                record_metric(metric_name, execution_time, MetricType.TIMER)
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                record_metric(f"{metric_name}_failed", execution_time, MetricType.TIMER)
                raise

        return wrapper

    return decorator


def monitor_cleanup_operation(category: str) -> Callable[..., Any]:
    """监控清理操作的装饰器"""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time

                # 记录执行时间
                record_metric(
                    "cleanup_execution_time",
                    execution_time,
                    MetricType.TIMER,
                    {"category": category},
                )

                # 记录清理记录数
                if isinstance(result, dict) and "records_cleaned" in result:
                    record_metric(
                        "cleanup_records_cleaned",
                        result["records_cleaned"],
                        MetricType.COUNTER,
                        {"category": category},
                    )

                # 记录成功率
                success = (
                    result.get("success", False) if isinstance(result, dict) else True
                )
                record_metric(
                    "cleanup_success",
                    1 if success else 0,
                    MetricType.COUNTER,
                    {"category": category},
                )

                return result

            except Exception as e:
                execution_time = time.time() - start_time

                # 记录失败指标
                record_metric(
                    "cleanup_execution_time",
                    execution_time,
                    MetricType.TIMER,
                    {"category": category, "status": "failed"},
                )
                record_metric(
                    "cleanup_failure", 1, MetricType.COUNTER, {"category": category}
                )

                # 发送告警
                send_alert(
                    AlertLevel.ERROR,
                    "data_cleanup",
                    f"清理操作失败 [{category}]: {e}",
                    {"category": category, "error": str(e)},
                )

                raise

        return wrapper

    return decorator


# 导出接口
__all__ = [
    "MonitoringService",
    "Alert",
    "Metric",
    "AlertLevel",
    "MetricType",
    "get_monitoring_service",
    "record_metric",
    "send_alert",
    "get_health_status",
    "monitor_execution_time",
    "monitor_cleanup_operation",
]
