"""Reddit Signal Scanner - 租户安全检测和告警机制

Linus设计原则："安全优先 + 自动化监控"
- 实时监控跨租户访问尝试
- 统一的安全事件记录和告警
- 非侵入式设计，不影响正常业务逻辑
- 可配置的告警策略和响应机制
"""

import logging
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, DefaultDict, Dict, List, Optional
from uuid import UUID  # noqa: F401  # 保留导入以兼容类型注解位置

from ..core.tenant_isolation import get_current_tenant_context
from .types import JsonValue

# 日志记录器
_logger = logging.getLogger(__name__)

# 安全事件全局计数器
_security_events: ContextVar[Dict[str, int]] = ContextVar(
    "security_events",
    default={},
)


class SecurityEventType(Enum):
    """安全事件类型枚举"""

    TENANT_VIOLATION = "tenant_violation"  # 租户违规访问
    UNAUTHORIZED_ACCESS = "unauthorized_access"  # 未授权访问
    PRIVILEGE_ESCALATION = "privilege_escalation"  # 权限提升尝试
    DATA_LEAK_ATTEMPT = "data_leak_attempt"  # 数据泄露尝试
    SUSPICIOUS_QUERY = "suspicious_query"  # 可疑查询
    SYSTEM_ABUSE = "system_abuse"  # 系统滥用


class SecurityLevel(Enum):
    """安全级别枚举"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityEvent:
    """安全事件数据结构"""

    event_type: SecurityEventType
    level: SecurityLevel
    message: str
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    target_user_id: Optional[str] = None
    target_resource: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: dict[str, JsonValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JsonValue]:
        """转换为字典格式"""
        return {
            "event_type": self.event_type.value,
            "level": self.level.value,
            "message": self.message,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "target_user_id": self.target_user_id,
            "target_resource": self.target_resource,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


class TenantSecurityMonitor:
    """
    租户安全监控器

    负责监控和记录租户安全事件，提供实时告警和统计。
    """

    def __init__(self) -> None:
        self.alert_handlers: List[Callable[[SecurityEvent], None]] = []
        self.event_history: List[SecurityEvent] = []
        self.max_history_size: int = 1000
        self._stats: Dict[str, int] = defaultdict(int)

    def add_alert_handler(
        self,
        handler: Callable[[SecurityEvent], None],
    ) -> None:
        """添加安全告警处理器"""
        self.alert_handlers.append(handler)

    def record_event(self, event: SecurityEvent) -> None:
        """
        记录安全事件

        Args:
            event: 安全事件
        """
        # 添加到历史记录
        self.event_history.append(event)

        # 保持历史记录大小
        if len(self.event_history) > self.max_history_size:
            self.event_history = self.event_history[-self.max_history_size :]

        # 更新统计
        self._stats[event.event_type.value] += 1
        self._stats[f"level_{event.level.value}"] += 1

        # 记录日志
        log_level = {
            SecurityLevel.LOW: logging.INFO,
            SecurityLevel.MEDIUM: logging.WARNING,
            SecurityLevel.HIGH: logging.ERROR,
            SecurityLevel.CRITICAL: logging.CRITICAL,
        }[event.level]

        _logger.log(
            log_level,
            (
                "🚨 安全事件: ["
                + event.level.value.upper()
                + "] "
                + event.message
                + " (user="
                + str(event.user_id)
                + ", target="
                + str(event.target_user_id)
                + ")"
            ),
        )

        # 触发告警处理器
        for handler in self.alert_handlers:
            try:
                handler(event)
            except Exception as e:
                _logger.error(f"安全告警处理器错误: {e}")

    def get_recent_events(
        self,
        minutes: int = 60,
        event_type: Optional[SecurityEventType] = None,
        level: Optional[SecurityLevel] = None,
    ) -> List[SecurityEvent]:
        """
        获取最近的安全事件

        Args:
            minutes: 时间范围（分钟）
            event_type: 事件类型过滤
            level: 安全级别过滤

        Returns:
            List[SecurityEvent]: 符合条件的事件列表
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)

        events = [
            event for event in self.event_history if event.timestamp >= cutoff_time
        ]

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if level:
            events = [e for e in events if e.level == level]

        return events

    def get_statistics(self) -> dict[str, JsonValue]:
        """获取安全统计信息"""
        recent_events = self.get_recent_events(60)  # 最近一小时

        return {
            "total_events": len(self.event_history),
            "recent_events_1h": len(recent_events),
            "event_type_stats": dict(self._stats),
            "recent_critical": len(
                [e for e in recent_events if e.level == SecurityLevel.CRITICAL]
            ),
            "recent_high": len(
                [e for e in recent_events if e.level == SecurityLevel.HIGH]
            ),
            "tenant_violations_1h": len(
                [
                    e
                    for e in recent_events
                    if e.event_type == SecurityEventType.TENANT_VIOLATION
                ]
            ),
        }

    def clear_history(self) -> None:
        """清空事件历史"""
        self.event_history.clear()
        self._stats.clear()
        _logger.info("安全事件历史已清空")


# 全局安全监控器实例
_security_monitor = TenantSecurityMonitor()


def get_security_monitor() -> TenantSecurityMonitor:
    """获取全局安全监控器"""
    return _security_monitor


# 安全事件记录函数
def record_tenant_violation(
    message: str,
    target_user_id: Optional[str] = None,
    target_resource: Optional[str] = None,
    level: SecurityLevel = SecurityLevel.HIGH,
    details: Optional[dict[str, JsonValue]] = None,
) -> None:
    """
    记录租户违规事件

    Args:
        message: 事件描述
        target_user_id: 目标用户ID
        target_resource: 目标资源
        level: 安全级别
        details: 附加细节
    """
    tenant_context = get_current_tenant_context()

    event = SecurityEvent(
        event_type=SecurityEventType.TENANT_VIOLATION,
        level=level,
        message=message,
        user_id=tenant_context.user_id if tenant_context else None,
        tenant_id=tenant_context.tenant_id if tenant_context else None,
        target_user_id=target_user_id,
        target_resource=target_resource,
        details=details or {},
    )

    _security_monitor.record_event(event)


def record_unauthorized_access(
    message: str,
    resource: str,
    action: Optional[str] = None,
    level: SecurityLevel = SecurityLevel.MEDIUM,
    details: Optional[dict[str, JsonValue]] = None,
) -> None:
    """
    记录未授权访问事件

    Args:
        message: 事件描述
        resource: 资源名称
        action: 操作类型
        level: 安全级别
        details: 附加细节
    """
    tenant_context = get_current_tenant_context()

    event = SecurityEvent(
        event_type=SecurityEventType.UNAUTHORIZED_ACCESS,
        level=level,
        message=message,
        user_id=tenant_context.user_id if tenant_context else None,
        tenant_id=tenant_context.tenant_id if tenant_context else None,
        target_resource=resource,
        details={"action": action, **(details or {})},
    )

    _security_monitor.record_event(event)


def record_suspicious_query(
    query_info: str,
    reason: str,
    level: SecurityLevel = SecurityLevel.MEDIUM,
    details: Optional[dict[str, JsonValue]] = None,
) -> None:
    """
    记录可疑查询事件

    Args:
        query_info: 查询信息
        reason: 可疑原因
        level: 安全级别
        details: 附加细节
    """
    tenant_context = get_current_tenant_context()

    event = SecurityEvent(
        event_type=SecurityEventType.SUSPICIOUS_QUERY,
        level=level,
        message=f"可疑查询: {reason}",
        user_id=tenant_context.user_id if tenant_context else None,
        tenant_id=tenant_context.tenant_id if tenant_context else None,
        details={"query": query_info, "reason": reason, **(details or {})},
    )

    _security_monitor.record_event(event)


# 自动化检测函数
def detect_cross_tenant_access(
    accessing_user_id: str, target_user_id: str, resource_type: str = "unknown"
) -> bool:
    """
    检测跨租户访问尝试

    Args:
        accessing_user_id: 访问者用户ID
        target_user_id: 目标用户ID
        resource_type: 资源类型

    Returns:
        bool: 是否检测到跨租户访问
    """
    # 在当前实现中，不同的user_id即为不同租户
    if accessing_user_id != target_user_id:
        record_tenant_violation(
            message=(
                f"跨租户访问尝试: 用户{accessing_user_id}尝试访问"
                f"用户{target_user_id}的{resource_type}"
            ),
            target_user_id=target_user_id,
            target_resource=resource_type,
            level=SecurityLevel.HIGH,
            details={
                "accessing_user": accessing_user_id,
                "target_user": target_user_id,
                "resource_type": resource_type,
            },
        )
        return True

    return False


def analyze_query_patterns(
    query_count: int, time_window_minutes: int = 5, threshold: int = 100
) -> None:
    """
    分析查询模式，检测异常行为

    Args:
        query_count: 查询数量
        time_window_minutes: 时间窗口（分钟）
        threshold: 告警阈值
    """
    if query_count > threshold:
        record_suspicious_query(
            query_info=f"{query_count} queries in {time_window_minutes} minutes",
            reason=f"查询频率异常高，超过阈值 {threshold}",
            level=SecurityLevel.MEDIUM,
            details={
                "query_count": query_count,
                "time_window": time_window_minutes,
                "threshold": threshold,
            },
        )


# 高级安全分析
class SecurityAnalyzer:
    """安全分析器 - 高级安全分析和建议"""

    def __init__(self, monitor: TenantSecurityMonitor):
        self.monitor = monitor

    def analyze_threat_patterns(
        self, time_window_hours: int = 24
    ) -> dict[str, JsonValue]:
        """
        分析威胁模式

        Args:
            time_window_hours: 分析时间窗口（小时）

        Returns:
            Dict[str, Any]: 威胁分析结果
        """
        events = self.monitor.get_recent_events(time_window_hours * 60)

        # 按用户分组分析
        user_events = defaultdict(list)
        for event in events:
            if event.user_id:
                user_events[event.user_id].append(event)

        # 检测高风险用户
        high_risk_users: List[dict[str, JsonValue]] = []
        for user_id, user_event_list in user_events.items():
            risk_score = self._calculate_risk_score(user_event_list)
            if risk_score > 7:  # 高风险阈值
                high_risk_users.append(
                    {
                        "user_id": user_id,
                        "risk_score": risk_score,
                        "event_count": len(user_event_list),
                        "violations": len(
                            [
                                e
                                for e in user_event_list
                                if e.event_type == SecurityEventType.TENANT_VIOLATION
                            ]
                        ),
                    }
                )

        return {
            "analysis_period_hours": time_window_hours,
            "total_events": len(events),
            "high_risk_users": high_risk_users,
            "event_summary": self._summarize_events(events),
            "recommendations": self._generate_recommendations(
                events,
                high_risk_users,
            ),
        }

    def _calculate_risk_score(self, events: List[SecurityEvent]) -> float:
        """计算用户风险评分"""
        score: float = 0.0

        for event in events:
            # 根据事件类型和级别计算分数
            type_scores = {
                SecurityEventType.TENANT_VIOLATION: 3,
                SecurityEventType.UNAUTHORIZED_ACCESS: 2,
                SecurityEventType.PRIVILEGE_ESCALATION: 4,
                SecurityEventType.DATA_LEAK_ATTEMPT: 5,
                SecurityEventType.SUSPICIOUS_QUERY: 1,
                SecurityEventType.SYSTEM_ABUSE: 2,
            }

            level_multipliers = {
                SecurityLevel.LOW: 0.5,
                SecurityLevel.MEDIUM: 1.0,
                SecurityLevel.HIGH: 2.0,
                SecurityLevel.CRITICAL: 3.0,
            }

            base_score = type_scores.get(event.event_type, 1)
            multiplier = level_multipliers.get(event.level, 1.0)
            score += base_score * multiplier

        return score

    def _summarize_events(self, events: List[SecurityEvent]) -> Dict[str, int]:
        """汇总事件统计"""
        summary: DefaultDict[str, int] = defaultdict(int)

        for event in events:
            summary[event.event_type.value] += 1
            summary[f"level_{event.level.value}"] += 1

        return dict(summary)

    def _generate_recommendations(
        self, events: List[SecurityEvent], high_risk_users: List[dict[str, JsonValue]]
    ) -> List[str]:
        """生成安全建议"""
        recommendations = []

        if high_risk_users:
            recommendations.append(f"发现 {len(high_risk_users)} 个高风险用户，建议加强监控")

        violation_count = sum(
            1 for e in events if e.event_type == SecurityEventType.TENANT_VIOLATION
        )
        if violation_count > 10:
            recommendations.append(f"检测到 {violation_count} 次租户违规，建议复查访问控制策略")

        critical_events = [e for e in events if e.level == SecurityLevel.CRITICAL]
        if critical_events:
            recommendations.append((f"发现 {len(critical_events)} 个关键安全事件，" "需要立即处理"))

        return recommendations


# 默认告警处理器
def default_security_alert_handler(event: SecurityEvent) -> None:
    """默认安全告警处理器"""
    if event.level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]:
        # 在实际环境中，这里可以发送邮件、Slack通知等
        _logger.critical(
            (
                f"🚨 紧急安全告警: {event.message} "
                f"[用户: {event.user_id}] [级别: {event.level.value}]"
            )
        )


# 初始化默认告警处理器
_security_monitor.add_alert_handler(default_security_alert_handler)


# ====================================================================
# 公开API
# ====================================================================

__all__ = [
    "SecurityEventType",
    "SecurityLevel",
    "SecurityEvent",
    "TenantSecurityMonitor",
    "SecurityAnalyzer",
    "get_security_monitor",
    "record_tenant_violation",
    "record_unauthorized_access",
    "record_suspicious_query",
    "detect_cross_tenant_access",
    "analyze_query_patterns",
]
