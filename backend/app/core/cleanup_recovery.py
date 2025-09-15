"""
清理错误恢复机制 - Reddit Signal Scanner
实现完整的故障检测、分析、恢复和预防机制

基于Linus设计原则：
- 简单的恢复策略，复杂的故障分析
- 自动恢复优于人工干预
- 防御性编程，预期错误发生
"""

import logging
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    TypedDict,
    TypeVar,
    Union,
    cast,
)

from ..core.cleanup_locks import get_cleanup_lock_manager
from ..services.data_cleanup_service import CleanupCategory, CleanupManager
from .types import JsonValue

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """故障类型枚举"""

    LOCK_TIMEOUT = "lock_timeout"
    DATABASE_ERROR = "database_error"
    PARAMETER_ERROR = "parameter_error"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    BUSINESS_LOGIC_ERROR = "business_logic_error"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    UNKNOWN_ERROR = "unknown_error"


class RecoveryAction(Enum):
    """恢复动作枚举"""

    RETRY_IMMEDIATELY = "retry_immediately"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    RETRY_WITH_REDUCED_SCOPE = "retry_with_reduced_scope"
    SKIP_AND_CONTINUE = "skip_and_continue"
    ABORT_WITH_CLEANUP = "abort_with_cleanup"
    ESCALATE_TO_HUMAN = "escalate_to_human"


class RecoveryContext(TypedDict, total=False):
    function_name: str
    args: Tuple[Any, ...]
    kwargs: dict[str, JsonValue]
    timestamp: str
    category: str


@dataclass
class FailureRecord:
    """故障记录数据结构"""

    failure_id: str
    failure_type: FailureType
    category: Optional[CleanupCategory]
    error_message: str
    stack_trace: str
    occurred_at: datetime
    context: RecoveryContext
    recovery_attempts: int = 0
    recovered: bool = False
    recovery_actions: List[RecoveryAction] = field(default_factory=list)


@dataclass
class RecoveryPlan:
    """恢复计划数据结构"""

    failure_record: FailureRecord
    recommended_actions: List[RecoveryAction]
    max_attempts: int
    backoff_multiplier: float
    timeout_seconds: int
    reduced_scope_params: Optional[dict[str, JsonValue]] = None


class FailureHistoryItem(TypedDict):
    failure_id: str
    failure_type: str
    category: Optional[str]
    error_message: str
    occurred_at: str
    recovery_attempts: int
    recovered: bool
    recovery_actions: List[str]


class RecoveryStats(TypedDict):
    total_failures: int
    successful_recoveries: int
    failed_recoveries: int
    escalated_to_human: int
    success_rate_percent: Union[int, float]
    generated_at: str


class FailureAnalyzer:
    """
    故障分析器 - 智能分析故障类型和恢复策略

    Linus原则：简单的规则，复杂的逻辑
    """

    def analyze_failure(
        self, exception: Exception, context: RecoveryContext
    ) -> FailureType:
        """
        分析故障类型

        Args:
            exception: 异常对象
            context: 故障上下文

        Returns:
            FailureType: 故障类型
        """
        error_message = str(exception).lower()
        # 移除未使用的局部变量，避免 F841：exception_type
        # exception_type = type(exception).__name__

        # 锁超时故障
        if "lock" in error_message or "timeout" in error_message:
            return FailureType.LOCK_TIMEOUT

        # 数据库错误
        if any(
            keyword in error_message
            for keyword in [
                "connection",
                "database",
                "sql",
                "postgresql",
                "deadlock",
            ]
        ):
            return FailureType.DATABASE_ERROR

        # 参数错误
        if any(
            keyword in error_message
            for keyword in ["parameter", "invalid", "value", "range"]
        ):
            return FailureType.PARAMETER_ERROR

        # 资源耗尽
        if any(
            keyword in error_message
            for keyword in ["memory", "disk", "resource", "quota", "limit"]
        ):
            return FailureType.RESOURCE_EXHAUSTED

        # 业务逻辑错误
        if "cleanup" in error_message or "records" in error_message:
            return FailureType.BUSINESS_LOGIC_ERROR

        # 外部服务错误
        if any(
            keyword in error_message
            for keyword in ["redis", "http", "network", "service", "api"]
        ):
            return FailureType.EXTERNAL_SERVICE_ERROR

        return FailureType.UNKNOWN_ERROR

    def create_recovery_plan(self, failure_record: FailureRecord) -> RecoveryPlan:
        """
        创建恢复计划 - 使用策略模式消除elif分支

        Args:
            failure_record: 故障记录

        Returns:
            RecoveryPlan: 恢复计划
        """
        failure_type = failure_record.failure_type

        # 策略模式：将每种故障类型的恢复策略封装为独立的创建器
        plan_creators = {
            FailureType.LOCK_TIMEOUT: self._create_lock_timeout_plan,
            FailureType.DATABASE_ERROR: self._create_database_error_plan,
            FailureType.PARAMETER_ERROR: self._create_parameter_error_plan,
            FailureType.RESOURCE_EXHAUSTED: self._create_resource_exhausted_plan,
            FailureType.BUSINESS_LOGIC_ERROR: self._create_business_logic_error_plan,
            FailureType.EXTERNAL_SERVICE_ERROR: self._create_external_service_error_plan,
            FailureType.UNKNOWN_ERROR: self._create_unknown_error_plan,
        }

        creator = plan_creators.get(failure_type, self._create_unknown_error_plan)
        return creator(failure_record)

    def _create_lock_timeout_plan(self, failure_record: FailureRecord) -> RecoveryPlan:
        """创建锁超时故障的恢复计划"""
        return RecoveryPlan(
            failure_record=failure_record,
            recommended_actions=[
                RecoveryAction.RETRY_WITH_BACKOFF,
                RecoveryAction.RETRY_WITH_REDUCED_SCOPE,
            ],
            max_attempts=5,
            backoff_multiplier=2.0,
            timeout_seconds=300,
        )

    def _create_database_error_plan(
        self, failure_record: FailureRecord
    ) -> RecoveryPlan:
        """创建数据库错误故障的恢复计划"""
        return RecoveryPlan(
            failure_record=failure_record,
            recommended_actions=[
                RecoveryAction.RETRY_WITH_BACKOFF,
                RecoveryAction.ABORT_WITH_CLEANUP,
            ],
            max_attempts=3,
            backoff_multiplier=1.5,
            timeout_seconds=600,
        )

    def _create_parameter_error_plan(
        self, failure_record: FailureRecord
    ) -> RecoveryPlan:
        """创建参数错误故障的恢复计划"""
        return RecoveryPlan(
            failure_record=failure_record,
            recommended_actions=[
                RecoveryAction.RETRY_WITH_REDUCED_SCOPE,
                RecoveryAction.SKIP_AND_CONTINUE,
            ],
            max_attempts=2,
            backoff_multiplier=1.0,
            timeout_seconds=60,
            reduced_scope_params=self._generate_safe_params(failure_record.context),
        )

    def _create_resource_exhausted_plan(
        self, failure_record: FailureRecord
    ) -> RecoveryPlan:
        """创建资源耗尽故障的恢复计划"""
        return RecoveryPlan(
            failure_record=failure_record,
            recommended_actions=[
                RecoveryAction.RETRY_WITH_REDUCED_SCOPE,
                RecoveryAction.RETRY_WITH_BACKOFF,
                RecoveryAction.ESCALATE_TO_HUMAN,
            ],
            max_attempts=3,
            backoff_multiplier=3.0,
            timeout_seconds=1800,
            reduced_scope_params=self._generate_minimal_params(failure_record.context),
        )

    def _create_business_logic_error_plan(
        self, failure_record: FailureRecord
    ) -> RecoveryPlan:
        """创建业务逻辑错误故障的恢复计划"""
        return RecoveryPlan(
            failure_record=failure_record,
            recommended_actions=[
                RecoveryAction.RETRY_WITH_REDUCED_SCOPE,
                RecoveryAction.SKIP_AND_CONTINUE,
            ],
            max_attempts=2,
            backoff_multiplier=1.0,
            timeout_seconds=120,
            reduced_scope_params=self._generate_conservative_params(
                failure_record.context
            ),
        )

    def _create_external_service_error_plan(
        self, failure_record: FailureRecord
    ) -> RecoveryPlan:
        """创建外部服务错误故障的恢复计划"""
        return RecoveryPlan(
            failure_record=failure_record,
            recommended_actions=[
                RecoveryAction.RETRY_WITH_BACKOFF,
                RecoveryAction.SKIP_AND_CONTINUE,
            ],
            max_attempts=4,
            backoff_multiplier=2.0,
            timeout_seconds=300,
        )

    def _create_unknown_error_plan(self, failure_record: FailureRecord) -> RecoveryPlan:
        """创建未知错误故障的恢复计划"""
        return RecoveryPlan(
            failure_record=failure_record,
            recommended_actions=[
                RecoveryAction.RETRY_IMMEDIATELY,
                RecoveryAction.RETRY_WITH_BACKOFF,
                RecoveryAction.ESCALATE_TO_HUMAN,
            ],
            max_attempts=3,
            backoff_multiplier=2.0,
            timeout_seconds=600,
        )

    def _generate_safe_params(self, context: RecoveryContext) -> dict[str, JsonValue]:
        """生成安全的参数 - 参数错误的缩小版"""
        return {
            "completed_task_days": 30,
            "failed_task_days": 7,
            "orphan_analysis_hours": 1.0,
            "inactive_user_days": 365,
        }

    def _generate_minimal_params(
        self, context: RecoveryContext
    ) -> dict[str, JsonValue]:
        """生成最小参数 - 资源耗尽的最小版"""
        return {
            "completed_task_days": 7,  # 大幅缩小范围
            "failed_task_days": 1,
            "orphan_analysis_hours": 0.5,
            "inactive_user_days": 90,
        }

    def _generate_conservative_params(
        self, context: RecoveryContext
    ) -> dict[str, JsonValue]:
        """生成保守参数 - 业务逻辑错误的保守版"""
        return {
            "completed_task_days": 14,  # 保守清理
            "failed_task_days": 3,
            "orphan_analysis_hours": 0.5,
            "inactive_user_days": 180,
        }


class CleanupRecoveryManager:
    """
    清理恢复管理器 - Linus架构合规版

    设计原则：
    1. 自动恢复优于人工干预
    2. 渐进式恢复策略（立即重试 → 延迟重试 → 缩小范围 → 跳过 → 上报）
    3. 完整的故障跟踪和分析
    4. 防止恢复循环和资源耗尽
    """

    def __init__(self) -> None:
        self.failure_analyzer = FailureAnalyzer()
        self.failure_history: Dict[str, FailureRecord] = {}
        self.recovery_stats = {
            "total_failures": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "escalated_to_human": 0,
        }

    def handle_cleanup_failure(
        self,
        exception: Exception,
        category: Optional[CleanupCategory],
        context: RecoveryContext,
    ) -> Tuple[bool, Optional[Any]]:
        """
        处理清理失败 - 主要入口点

        Args:
            exception: 异常对象
            category: 清理类别
            context: 故障上下文

        Returns:
            Tuple[bool, Optional[Any]]: (是否恢复成功, 恢复结果)
        """
        # 创建故障记录
        failure_record = self._create_failure_record(exception, category, context)

        # 分析故障并创建恢复计划
        recovery_plan = self.failure_analyzer.create_recovery_plan(failure_record)

        # 执行恢复计划
        success, result = self._execute_recovery_plan(recovery_plan)

        # 更新统计信息
        self._update_recovery_stats(success, recovery_plan)

        # 记录恢复结果
        failure_record.recovered = success
        self.failure_history[failure_record.failure_id] = failure_record

        if success:
            logger.info(f"故障恢复成功: {failure_record.failure_id}")
        else:
            logger.error(f"故障恢复失败: {failure_record.failure_id}")

        return success, result

    def _create_failure_record(
        self,
        exception: Exception,
        category: Optional[CleanupCategory],
        context: RecoveryContext,
    ) -> FailureRecord:
        """创建故障记录"""
        failure_id = (
            f"{int(time.time() * 1000)}_{category.value if category else 'unknown'}"
        )
        failure_type = self.failure_analyzer.analyze_failure(exception, context)

        return FailureRecord(
            failure_id=failure_id,
            failure_type=failure_type,
            category=category,
            error_message=str(exception),
            stack_trace=traceback.format_exc(),
            occurred_at=datetime.now(timezone.utc),
            context=context.copy(),
        )

    def _execute_recovery_plan(self, plan: RecoveryPlan) -> Tuple[bool, Optional[Any]]:
        """执行恢复计划"""
        failure_record = plan.failure_record

        for attempt in range(plan.max_attempts):
            failure_record.recovery_attempts = attempt + 1

            for action in plan.recommended_actions:
                try:
                    success, result = self._execute_recovery_action(
                        action, plan, attempt
                    )

                    if success:
                        failure_record.recovery_actions.append(action)
                        return True, result

                except Exception as recovery_error:
                    logger.warning(
                        f"恢复动作 {action.value} 失败: {recovery_error}",
                        extra={"failure_id": failure_record.failure_id},
                    )
                    continue

            # 如果所有动作都失败，等待后重试
            if attempt < plan.max_attempts - 1:
                backoff_time = plan.backoff_multiplier**attempt
                logger.info(f"恢复尝试 {attempt + 1} 失败，等待 {backoff_time} 秒后重试")
                time.sleep(backoff_time)

        # 所有尝试都失败，最后执行升级动作
        return self._escalate_failure(failure_record)

    def _execute_recovery_action(
        self, action: RecoveryAction, plan: RecoveryPlan, attempt: int
    ) -> Tuple[bool, Optional[Any]]:
        """执行具体的恢复动作 - 使用策略模式消除elif分支"""
        # 移除未使用的局部变量，避免 F841
        # context = plan.failure_record.context
        # category = plan.failure_record.category

        # 策略模式：将每个恢复动作封装为独立的处理器
        action_handlers = {
            RecoveryAction.RETRY_IMMEDIATELY: self._handle_retry_immediately,
            RecoveryAction.RETRY_WITH_BACKOFF: self._handle_retry_with_backoff,
            RecoveryAction.RETRY_WITH_REDUCED_SCOPE: self._handle_retry_with_reduced_scope,
            RecoveryAction.SKIP_AND_CONTINUE: self._handle_skip_and_continue,
            RecoveryAction.ABORT_WITH_CLEANUP: self._handle_abort_with_cleanup,
            RecoveryAction.ESCALATE_TO_HUMAN: self._handle_escalate_to_human,
        }

        handler = action_handlers.get(action)
        if handler:
            return handler(plan, attempt)

        return False, None

    def _handle_retry_immediately(
        self, plan: RecoveryPlan, attempt: int
    ) -> Tuple[bool, Optional[Any]]:
        """处理立即重试恢复动作"""
        fr = plan.failure_record
        return self._retry_cleanup(
            fr.category,
            self._extract_kwargs_for_retry(fr.context),
        )

    def _handle_retry_with_backoff(
        self, plan: RecoveryPlan, attempt: int
    ) -> Tuple[bool, Optional[Any]]:
        """处理延迟重试恢复动作"""
        fr = plan.failure_record
        backoff_time = plan.backoff_multiplier**attempt
        logger.info(f"延迟 {backoff_time} 秒后重试清理")
        time.sleep(backoff_time)
        return self._retry_cleanup(
            fr.category,
            self._extract_kwargs_for_retry(fr.context),
        )

    def _handle_retry_with_reduced_scope(
        self, plan: RecoveryPlan, attempt: int
    ) -> Tuple[bool, Optional[Any]]:
        """处理缩小范围重试恢复动作"""
        fr = plan.failure_record
        if plan.reduced_scope_params:
            logger.info("使用缩小范围的参数重试清理")
            return self._retry_cleanup(fr.category, plan.reduced_scope_params)
        else:
            return self._retry_cleanup(
                fr.category,
                self._extract_kwargs_for_retry(fr.context),
            )

    def _handle_skip_and_continue(
        self, plan: RecoveryPlan, attempt: int
    ) -> Tuple[bool, Optional[Any]]:
        """处理跳过并继续恢复动作"""
        fr = plan.failure_record
        category = fr.category
        logger.info(f"跳过清理类别 {category.value if category else 'unknown'}，继续其他清理")
        return True, {
            "skipped": True,
            "category": category.value if category else None,
        }

    def _handle_abort_with_cleanup(
        self, plan: RecoveryPlan, attempt: int
    ) -> Tuple[bool, Optional[Any]]:
        """处理中止并清理恢复动作"""
        fr = plan.failure_record
        logger.info("中止清理并执行清理操作")
        self._cleanup_partial_operations(fr)
        return False, {"aborted": True, "cleaned_up": True}

    def _handle_escalate_to_human(
        self, plan: RecoveryPlan, attempt: int
    ) -> Tuple[bool, Optional[Any]]:
        """处理升级到人工处理恢复动作"""
        return self._escalate_failure(plan.failure_record)

    def _retry_cleanup(
        self, category: Optional[CleanupCategory], params: dict[str, JsonValue]
    ) -> Tuple[bool, Optional[Any]]:
        """重试清理操作"""
        try:
            with CleanupManager() as cleanup_service:
                if category:
                    # 单个类别清理
                    result = cleanup_service.cleanup_by_category(
                        category.value, **params
                    )
                    return result["success"], result
                else:
                    # 完整清理
                    result = cleanup_service.execute_full_cleanup(**params)
                    return result["success"], result

        except Exception as e:
            logger.error(f"重试清理失败: {e}")
            return False, None

    def _cleanup_partial_operations(self, failure_record: FailureRecord) -> None:
        """清理部分操作（释放资源、回滚事务等）"""
        try:
            # 释放可能持有的锁
            lock_manager = get_cleanup_lock_manager()

            if failure_record.category:
                lock = lock_manager.get_lock(failure_record.category)
                if lock.is_locked():
                    logger.info(f"释放清理锁: {failure_record.category.value}")
                    lock.release()

            # TODO: 其他清理操作（临时文件、数据库连接等）

        except Exception as cleanup_error:
            logger.error(f"清理部分操作失败: {cleanup_error}")

    def _escalate_failure(
        self, failure_record: FailureRecord
    ) -> Tuple[bool, Optional[Any]]:
        """升级失败到人工处理"""
        extra_data = {
            "failure_type": failure_record.failure_type.value,
            "category": (
                failure_record.category.value if failure_record.category else None
            ),
            "error_message": failure_record.error_message,
            "recovery_attempts": failure_record.recovery_attempts,
        }
        logger.error(f"故障升级到人工处理: {failure_record.failure_id}", extra=extra_data)

        # TODO: 发送告警通知（邮件、钉钉、企微等）
        # TODO: 记录到故障管理系统

        escalation_result = {
            "escalated": True,
            "failure_id": failure_record.failure_id,
            "contact_oncall": True,
        }

        return False, escalation_result

    def _update_recovery_stats(self, success: bool, plan: RecoveryPlan) -> None:
        """更新恢复统计信息"""
        self.recovery_stats["total_failures"] += 1

        if success:
            self.recovery_stats["successful_recoveries"] += 1
        else:
            self.recovery_stats["failed_recoveries"] += 1

            # 检查是否升级到人工
            if RecoveryAction.ESCALATE_TO_HUMAN in plan.recommended_actions:
                self.recovery_stats["escalated_to_human"] += 1

    def get_failure_history(self, hours: int = 24) -> List[FailureHistoryItem]:
        """获取故障历史"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        recent_failures: List[FailureHistoryItem] = []
        for failure_id, record in self.failure_history.items():
            if record.occurred_at >= cutoff_time:
                recent_failures.append(
                    {
                        "failure_id": failure_id,
                        "failure_type": record.failure_type.value,
                        "category": record.category.value if record.category else None,
                        "error_message": record.error_message,
                        "occurred_at": record.occurred_at.isoformat(),
                        "recovery_attempts": record.recovery_attempts,
                        "recovered": record.recovered,
                        "recovery_actions": [
                            action.value for action in record.recovery_actions
                        ],
                    }
                )

        return sorted(recent_failures, key=lambda x: x["occurred_at"], reverse=True)

    def get_recovery_statistics(self) -> RecoveryStats:
        """获取恢复统计信息"""
        total = self.recovery_stats["total_failures"]
        success_rate: float
        if total == 0:
            success_rate = 0.0
        else:
            success_rate = round(
                (self.recovery_stats["successful_recoveries"] / total) * 100.0, 2
            )

        return {
            "total_failures": int(self.recovery_stats.get("total_failures", 0)),
            "successful_recoveries": int(
                self.recovery_stats.get("successful_recoveries", 0)
            ),
            "failed_recoveries": int(self.recovery_stats.get("failed_recoveries", 0)),
            "escalated_to_human": int(self.recovery_stats.get("escalated_to_human", 0)),
            "success_rate_percent": success_rate,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _extract_kwargs_for_retry(
        self, context: RecoveryContext
    ) -> dict[str, JsonValue]:
        """从恢复上下文中提取用于重试的参数字典。"""
        raw = context.get("kwargs")
        if raw is None:
            return {}
        return raw

    def cleanup_old_records(self, days: int = 7) -> None:
        """清理旧的故障记录"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)

        old_failure_ids = [
            failure_id
            for failure_id, record in self.failure_history.items()
            if record.occurred_at < cutoff_time
        ]

        for failure_id in old_failure_ids:
            del self.failure_history[failure_id]

        logger.info(f"清理了 {len(old_failure_ids)} 个旧故障记录")


# 全局恢复管理器实例
_recovery_manager = None


def get_cleanup_recovery_manager() -> CleanupRecoveryManager:
    """获取全局清理恢复管理器"""
    global _recovery_manager

    if _recovery_manager is None:
        _recovery_manager = CleanupRecoveryManager()

    return _recovery_manager


# 便捷装饰器
T = TypeVar("T")


def with_cleanup_recovery(
    category: Optional[CleanupCategory] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    清理恢复装饰器 - 自动处理清理失败和恢复

    Args:
        category: 清理类别
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                recovery_manager = get_cleanup_recovery_manager()

                context: RecoveryContext = {
                    "function_name": func.__name__,
                    "args": args,
                    "kwargs": kwargs,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                success, result = recovery_manager.handle_cleanup_failure(
                    e, category, context
                )

                if success:
                    return cast(T, result)
                else:
                    # 恢复失败，重新抛出原异常
                    raise e

        return wrapper

    return decorator


# 导出接口
__all__ = [
    "CleanupRecoveryManager",
    "FailureRecord",
    "RecoveryPlan",
    "FailureType",
    "RecoveryAction",
    "get_cleanup_recovery_manager",
    "with_cleanup_recovery",
]
