"""
失败模式分析器

智能分析任务失败模式，提供：
- 常见失败模式识别和分类
- 自动恢复建议生成
- 失败率统计和告警
- 基于模式的预防性建议

Linus原则应用：
1. 数据结构决定一切 - 模式匹配规则驱动分析逻辑
2. 消除特殊情况 - 统一的模式匹配框架，无特殊分支
3. 简单胜过聪明 - 直观的模式定义，清晰的建议输出
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple, Union

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from pydantic import BaseModel
from sqlalchemy import and_, desc, func

from ..core.database import get_db
from ..core.sqlalchemy_typing import as_bool_clause
from ..models.task import FailureCategory, Task, TaskStatus


class FailureSeverity(str, Enum):
    """失败严重程度"""

    LOW = "low"  # 偶发性失败，影响较小
    MEDIUM = "medium"  # 中等频率失败，需要关注
    HIGH = "high"  # 高频失败，需要立即处理
    CRITICAL = "critical"  # 严重失败，影响系统稳定性


class RecoveryAction(str, Enum):
    """恢复操作类型"""

    RETRY_WITH_DELAY = "retry_with_delay"  # 延迟重试
    ADJUST_PARAMETERS = "adjust_parameters"  # 调整参数
    SCALE_RESOURCES = "scale_resources"  # 扩展资源
    MANUAL_INTERVENTION = "manual_intervention"  # 人工介入
    IGNORE_TEMPORARILY = "ignore_temporarily"  # 暂时忽略


@dataclass
class FailurePattern:
    """失败模式定义"""

    pattern_id: str  # 模式唯一标识
    name: str  # 模式名称
    description: str  # 模式描述
    regex_patterns: List[str]  # 正则匹配模式列表
    failure_category: FailureCategory  # 失败分类
    severity: FailureSeverity = FailureSeverity.MEDIUM  # 严重程度
    auto_recoverable: bool = True  # 是否可自动恢复
    recovery_actions: List[RecoveryAction] = field(default_factory=list)  # 恢复建议
    occurrence_threshold: int = 5  # 触发告警的出现次数阈值
    time_window_hours: int = 24  # 统计时间窗口


@dataclass
class FailureAnalysisResult:
    """失败分析结果"""

    pattern_id: Optional[str]  # 匹配的模式ID
    pattern_name: Optional[str]  # 模式名称
    confidence: float  # 匹配置信度 (0-1)
    failure_category: FailureCategory  # 失败分类
    severity: FailureSeverity  # 严重程度
    recovery_suggestions: List[str]  # 恢复建议
    auto_recoverable: bool  # 是否可自动恢复
    similar_failures_count: int  # 相似失败数量
    trend_analysis: Dict[str, Union[str, int, float]]  # 趋势分析


class FailureAlert(BaseModel):
    """失败告警"""

    alert_id: str  # 告警ID
    pattern_id: str  # 相关模式
    severity: FailureSeverity  # 严重程度
    occurrence_count: int  # 发生次数
    time_window: str  # 时间窗口
    affected_tasks: List[str]  # 影响的任务ID
    suggested_actions: List[str]  # 建议操作
    alert_timestamp: datetime  # 告警时间


class FailureAnalyzer:
    """失败模式分析器

    核心功能：
    - 基于预定义模式识别失败类型
    - 生成智能恢复建议
    - 监控失败趋势和告警
    - 提供预防性维护建议
    """

    def __init__(self) -> None:
        self.failure_patterns = self._init_failure_patterns()
        self.pattern_cache: Dict[str, FailureAnalysisResult] = {}

    def _init_failure_patterns(self) -> List[FailurePattern]:
        """初始化失败模式库"""
        return [
            # Reddit API限流错误
            FailurePattern(
                pattern_id="reddit_rate_limit",
                name="Reddit API Rate Limit",
                description="Reddit API调用频率超限",
                regex_patterns=[
                    r"rate.?limit.?exceeded",
                    r"too.?many.?requests",
                    r"429.*reddit",
                    r"quota.?exceeded",
                ],
                failure_category=FailureCategory.NETWORK_ERROR,
                severity=FailureSeverity.MEDIUM,
                auto_recoverable=True,
                recovery_actions=[
                    RecoveryAction.RETRY_WITH_DELAY,
                    RecoveryAction.ADJUST_PARAMETERS,
                ],
                occurrence_threshold=10,
                time_window_hours=1,
            ),
            # 网络连接问题
            FailurePattern(
                pattern_id="network_connectivity",
                name="Network Connectivity Issues",
                description="网络连接失败或超时",
                regex_patterns=[
                    r"connection.?(refused|reset|timeout|failed)",
                    r"network.?(error|unreachable)",
                    r"dns.?(resolution|lookup).?fail",
                    r"socket.?(timeout|error)",
                ],
                failure_category=FailureCategory.NETWORK_ERROR,
                severity=FailureSeverity.HIGH,
                auto_recoverable=True,
                recovery_actions=[
                    RecoveryAction.RETRY_WITH_DELAY,
                    RecoveryAction.MANUAL_INTERVENTION,
                ],
                occurrence_threshold=5,
                time_window_hours=6,
            ),
            # 内存不足错误
            FailurePattern(
                pattern_id="memory_exhaustion",
                name="Memory Exhaustion",
                description="系统内存不足导致的失败",
                regex_patterns=[
                    r"memory.?error",
                    r"out.?of.?memory",
                    r"cannot.?allocate.?memory",
                    r"memoryerror",
                ],
                failure_category=FailureCategory.SYSTEM_ERROR,
                severity=FailureSeverity.CRITICAL,
                auto_recoverable=False,
                recovery_actions=[
                    RecoveryAction.SCALE_RESOURCES,
                    RecoveryAction.MANUAL_INTERVENTION,
                ],
                occurrence_threshold=3,
                time_window_hours=12,
            ),
            # 数据验证失败
            FailurePattern(
                pattern_id="data_validation",
                name="Data Validation Failure",
                description="输入数据格式或内容验证失败",
                regex_patterns=[
                    r"validation.?(error|failed)",
                    r"invalid.?(format|data|input)",
                    r"schema.?(validation|error)",
                    r"parse.?(error|failed)",
                ],
                failure_category=FailureCategory.DATA_VALIDATION_ERROR,
                severity=FailureSeverity.LOW,
                auto_recoverable=False,
                recovery_actions=[
                    RecoveryAction.MANUAL_INTERVENTION,
                    RecoveryAction.ADJUST_PARAMETERS,
                ],
                occurrence_threshold=15,
                time_window_hours=24,
            ),
            # 处理超时
            FailurePattern(
                pattern_id="processing_timeout",
                name="Processing Timeout",
                description="任务处理超时",
                regex_patterns=[
                    r"timeout.?(error|exceeded)",
                    r"processing.?timeout",
                    r"operation.?timed.?out",
                    r"deadline.?exceeded",
                ],
                failure_category=FailureCategory.PROCESSING_ERROR,
                severity=FailureSeverity.MEDIUM,
                auto_recoverable=True,
                recovery_actions=[
                    RecoveryAction.RETRY_WITH_DELAY,
                    RecoveryAction.ADJUST_PARAMETERS,
                    RecoveryAction.SCALE_RESOURCES,
                ],
                occurrence_threshold=8,
                time_window_hours=4,
            ),
            # 权限问题
            FailurePattern(
                pattern_id="permission_denied",
                name="Permission Denied",
                description="权限不足或认证失败",
                regex_patterns=[
                    r"permission.?denied",
                    r"access.?denied",
                    r"unauthorized",
                    r"authentication.?(failed|error)",
                    r"403.*forbidden",
                ],
                failure_category=FailureCategory.SYSTEM_ERROR,
                severity=FailureSeverity.HIGH,
                auto_recoverable=False,
                recovery_actions=[
                    RecoveryAction.MANUAL_INTERVENTION,
                    RecoveryAction.ADJUST_PARAMETERS,
                ],
                occurrence_threshold=3,
                time_window_hours=24,
            ),
        ]

    def analyze_failure(
        self,
        error_message: str,
        exception_type: str,
        task: Optional[Task] = None,
        db_session: Optional["Session"] = None,
    ) -> FailureAnalysisResult:
        """分析单个失败，识别模式并生成建议

        Args:
            error_message: 错误信息
            exception_type: 异常类型
            task: 相关任务（可选）
            db_session: 数据库会话（用于历史分析）

        Returns:
            失败分析结果
        """
        # 构建完整的错误上下文
        full_error_context = f"{exception_type}: {error_message}".lower()

        # 检查缓存
        context_hash = str(hash(full_error_context))
        if context_hash in self.pattern_cache:
            cached_result = self.pattern_cache[context_hash]
            # 更新相似失败数量（如果有数据库会话）
            if db_session:
                cached_result.similar_failures_count = self._count_similar_failures(
                    cached_result.pattern_id, db_session
                )
            return cached_result

        # 模式匹配分析
        best_match = self._match_failure_pattern(full_error_context)

        # 生成分析结果
        if best_match:
            pattern, confidence = best_match
            recovery_suggestions = self._generate_recovery_suggestions(pattern, task)
            similar_count = (
                self._count_similar_failures(pattern.pattern_id, db_session)
                if db_session
                else 0
            )

            result = FailureAnalysisResult(
                pattern_id=pattern.pattern_id,
                pattern_name=pattern.name,
                confidence=confidence,
                failure_category=pattern.failure_category,
                severity=pattern.severity,
                recovery_suggestions=recovery_suggestions,
                auto_recoverable=pattern.auto_recoverable,
                similar_failures_count=similar_count,
                trend_analysis=(
                    self._analyze_failure_trend(pattern.pattern_id, db_session)
                    if db_session
                    else {}
                ),
            )
        else:
            # 未匹配到已知模式
            result = FailureAnalysisResult(
                pattern_id=None,
                pattern_name="Unknown Pattern",
                confidence=0.0,
                failure_category=FailureCategory.SYSTEM_ERROR,  # 默认分类
                severity=FailureSeverity.MEDIUM,
                recovery_suggestions=["请检查错误日志并考虑手动重试"],
                auto_recoverable=False,
                similar_failures_count=0,
                trend_analysis={},
            )

        # 缓存结果（限制缓存大小）
        if len(self.pattern_cache) < 1000:
            self.pattern_cache[context_hash] = result

        return result

    def _match_failure_pattern(
        self, error_context: str
    ) -> Optional[Tuple[FailurePattern, float]]:
        """匹配失败模式，返回最佳匹配和置信度"""
        best_match = None
        best_confidence = 0.0

        for pattern in self.failure_patterns:
            confidence = self._calculate_pattern_confidence(pattern, error_context)

            if confidence > best_confidence and confidence > 0.5:  # 最低置信度阈值
                best_confidence = confidence
                best_match = pattern

        return (best_match, best_confidence) if best_match else None

    def _calculate_pattern_confidence(
        self, pattern: FailurePattern, error_context: str
    ) -> float:
        """计算模式匹配置信度"""
        matches = 0
        total_patterns = len(pattern.regex_patterns)

        for regex_pattern in pattern.regex_patterns:
            try:
                if re.search(regex_pattern, error_context, re.IGNORECASE):
                    matches += 1
            except re.error:
                # 正则表达式错误，跳过
                continue

        return matches / total_patterns if total_patterns > 0 else 0.0

    def _generate_recovery_suggestions(
        self, pattern: FailurePattern, task: Optional[Task]
    ) -> List[str]:
        """根据失败模式生成恢复建议"""
        suggestions = []

        for action in pattern.recovery_actions:
            if action == RecoveryAction.RETRY_WITH_DELAY:
                suggestions.append("等待一段时间后重试任务")
            elif action == RecoveryAction.ADJUST_PARAMETERS:
                suggestions.append("检查并调整任务参数或配置")
            elif action == RecoveryAction.SCALE_RESOURCES:
                suggestions.append("考虑增加系统资源或优化任务处理")
            elif action == RecoveryAction.MANUAL_INTERVENTION:
                suggestions.append("需要人工检查和处理")
            elif action == RecoveryAction.IGNORE_TEMPORARILY:
                suggestions.append("可暂时忽略，监控后续情况")

        # 添加模式特定的建议
        if pattern.pattern_id == "reddit_rate_limit":
            suggestions.append("建议降低Reddit API调用频率或升级API限额")
        elif pattern.pattern_id == "memory_exhaustion":
            suggestions.append("建议优化数据处理逻辑或增加内存资源")
        elif pattern.pattern_id == "network_connectivity":
            suggestions.append("检查网络连接状态和DNS配置")

        return suggestions

    def _count_similar_failures(
        self,
        pattern_id: Optional[str],
        db_session: "Session",
        time_window_hours: int = 24,
    ) -> int:
        """统计相似失败数量"""
        if not pattern_id or not db_session:
            return 0

        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)

        # 通过error_message模糊匹配统计
        # 这里简化处理，实际可以用更复杂的相似度算法
        count = (
            db_session.query(Task)
            .filter(
                as_bool_clause(
                    and_(
                        Task.status.in_(
                            [TaskStatus.FAILED.value, TaskStatus.DEAD_LETTER.value]
                        ),
                        Task.updated_at >= cutoff_time,
                        Task.error_message.isnot(None),
                    )
                )
            )
            .count()
        )

        return count

    def _analyze_failure_trend(
        self, pattern_id: Optional[str], db_session: "Session", days: int = 7
    ) -> Dict[str, Union[str, int, float]]:
        """分析失败趋势"""
        if not pattern_id or not db_session:
            return {}

        # 按天统计失败数量
        cutoff_time = datetime.utcnow() - timedelta(days=days)

        daily_failures = (
            db_session.query(
                func.date(Task.updated_at).label("date"),
                func.count(Task.id).label("count"),
            )
            .filter(
                as_bool_clause(
                    and_(
                        Task.status.in_(
                            [TaskStatus.FAILED.value, TaskStatus.DEAD_LETTER.value]
                        ),
                        Task.updated_at >= cutoff_time,
                    )
                )
            )
            .group_by(func.date(Task.updated_at))
            .all()
        )

        # 计算趋势
        failure_counts = [row[1] for row in daily_failures]
        if len(failure_counts) >= 2:
            trend = (
                "increasing" if failure_counts[-1] > failure_counts[0] else "decreasing"
            )
            avg_daily = sum(failure_counts) / len(failure_counts)
        else:
            trend = "stable"
            avg_daily = failure_counts[0] if failure_counts else 0

        return {
            "trend": trend,
            "avg_daily_failures": avg_daily,
            "total_failures": sum(failure_counts),
            "analysis_period_days": days,
        }

    def get_failure_statistics(
        self, db_session: "Session", time_window_hours: int = 24
    ) -> Dict[str, Union[int, List[Dict[str, str]], str, Dict[str, int]]]:
        """获取失败统计信息"""
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)

        # 按失败分类统计
        category_stats = (
            db_session.query(Task.failure_category, func.count(Task.id).label("count"))
            .filter(
                as_bool_clause(
                    and_(
                        Task.status.in_(
                            [TaskStatus.FAILED.value, TaskStatus.DEAD_LETTER.value]
                        ),
                        Task.updated_at >= cutoff_time,
                    )
                )
            )
            .group_by(Task.failure_category)
            .all()
        )

        # 检查是否需要发送告警
        alerts = self._check_failure_alerts(db_session)

        return {
            "time_window_hours": time_window_hours,
            "failure_by_category": {
                row[0] or "unknown": row[1] for row in category_stats
            },
            "total_failures": sum(row[1] for row in category_stats),
            "alerts": [alert.dict() for alert in alerts],
            "analysis_timestamp": datetime.utcnow().isoformat(),
        }

    def _check_failure_alerts(self, db_session: "Session") -> List[FailureAlert]:
        """检查是否需要发送失败告警"""
        alerts = []

        for pattern in self.failure_patterns:
            # 检查模式在时间窗口内的出现次数
            cutoff_time = datetime.utcnow() - timedelta(hours=pattern.time_window_hours)

            # 这里简化处理，实际需要更精确的模式匹配统计
            failure_count = (
                db_session.query(Task)
                .filter(
                    as_bool_clause(
                        and_(
                            Task.status.in_(
                                [TaskStatus.FAILED.value, TaskStatus.DEAD_LETTER.value]
                            ),
                            Task.updated_at >= cutoff_time,
                            Task.failure_category == pattern.failure_category.value,
                        )
                    )
                )
                .count()
            )

            if failure_count >= pattern.occurrence_threshold:
                # 生成告警
                alert = FailureAlert(
                    alert_id=f"{pattern.pattern_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    pattern_id=pattern.pattern_id,
                    severity=pattern.severity,
                    occurrence_count=failure_count,
                    time_window=f"{pattern.time_window_hours}h",
                    affected_tasks=[],  # TODO: 获取具体受影响的任务ID
                    suggested_actions=[
                        action.value for action in pattern.recovery_actions
                    ],
                    alert_timestamp=datetime.utcnow(),
                )
                alerts.append(alert)

        return alerts

    def suggest_preventive_actions(
        self, db_session: "Session"
    ) -> List[Dict[str, Union[str, int]]]:
        """基于历史失败数据建议预防性操作"""
        suggestions: List[Dict[str, Union[str, int]]] = []

        # 分析高频失败模式
        failure_patterns = self._identify_high_frequency_patterns(db_session)

        for pattern_id, count in failure_patterns.items():
            pattern = next(
                (p for p in self.failure_patterns if p.pattern_id == pattern_id), None
            )
            if pattern and count > pattern.occurrence_threshold:
                suggestions.append(
                    {
                        "pattern": pattern.name,
                        "description": pattern.description,
                        "frequency": int(count),
                        "suggested_prevention": self._get_prevention_suggestion(
                            pattern
                        ),
                        "priority": pattern.severity.value,
                    }
                )

        return suggestions

    def _identify_high_frequency_patterns(
        self, db_session: "Session"
    ) -> Dict[str, int]:
        """识别高频失败模式"""
        # 简化实现：按失败分类统计
        # 实际应该基于更精确的模式匹配
        recent_failures = (
            db_session.query(Task)
            .filter(
                as_bool_clause(
                    and_(
                        Task.status.in_(
                            [TaskStatus.FAILED.value, TaskStatus.DEAD_LETTER.value]
                        ),
                        Task.updated_at >= datetime.utcnow() - timedelta(days=7),
                    )
                )
            )
            .all()
        )

        pattern_counts: Dict[str, int] = defaultdict(int)
        for task in recent_failures:
            if task.failure_category:
                # 根据失败分类映射到模式
                for pattern in self.failure_patterns:
                    if pattern.failure_category.value == task.failure_category:
                        pattern_counts[pattern.pattern_id] += 1
                        break

        return dict(pattern_counts)

    def _get_prevention_suggestion(self, pattern: FailurePattern) -> str:
        """获取预防建议"""
        if pattern.pattern_id == "reddit_rate_limit":
            return "实施更智能的API调用频率控制和缓存策略"
        elif pattern.pattern_id == "memory_exhaustion":
            return "优化数据处理算法，实施内存使用监控"
        elif pattern.pattern_id == "network_connectivity":
            return "实施网络健康检查和自动重连机制"
        elif pattern.pattern_id == "processing_timeout":
            return "优化处理逻辑，增加超时配置的自适应调整"
        else:
            return "监控相关指标，制定针对性的预防措施"


# 全局失败分析器实例
failure_analyzer = FailureAnalyzer()


def get_failure_analyzer() -> FailureAnalyzer:
    """获取失败分析器实例"""
    return failure_analyzer
