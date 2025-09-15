"""
死信队列处理器

管理重试失败的任务，提供：
- 死信队列生命周期管理
- 手动重试接口
- 死信队列监控和统计
- 批量恢复操作

Linus原则应用：
1. 数据结构决定一切 - 基于Task模型的dead_letter状态
2. 消除特殊情况 - 统一的死信处理流程，无论失败原因
3. 简单胜过聪明 - 直观的API设计，清晰的状态转换
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    NoReturn,
    Optional,
    Tuple,
    TypedDict,
    cast,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from pydantic import BaseModel
from sqlalchemy import and_, func, or_

from ..core.database import get_db
from ..core.sqlalchemy_typing import as_bool_clause
from ..models.task import FailureCategory, Task, TaskStatus

# from ..core.exceptions import DeadLetterException, ValidationException  # 不存在的异常，使用通用异常替代
# 可选的重试策略（在缺失模块时使用默认空实现）
# 先定义带类型的占位符变量，避免在失败分支赋 None 导致类型逃逸
_real_get_retry_policy: Optional[Callable[[], Any]]
try:
    from ..core.retry_policy import get_retry_policy as _imported_get_retry_policy
    _real_get_retry_policy = _imported_get_retry_policy
except Exception:  # pragma: no cover
    _real_get_retry_policy = None


from ..core.types import ConfigDict
from typing import Optional, Any, Callable
import logging


_real_get_retry_policy_typed: Optional[Callable[[], Any]]
try:  # 将动态导入的对象规范为可选可调用，避免 mypy 判定恒真/恒假
    # 如果上方 try 成功，则 _real_get_retry_policy 已绑定为实现
    _real_get_retry_policy_typed = _real_get_retry_policy
except Exception:
    _real_get_retry_policy_typed = None


def get_retry_policy() -> Optional[Any]:
    """获取重试策略；在缺失实现时返回 None（优雅降级）。"""
    impl = _real_get_retry_policy_typed
    if impl is None:
        return None
    return impl()


class DeadLetterAction(str, Enum):
    """死信队列操作类型"""

    MANUAL_RETRY = "manual_retry"  # 手动重试
    BATCH_RETRY = "batch_retry"  # 批量重试
    ARCHIVE = "archive"  # 归档
    DELETE = "delete"  # 删除


@dataclass
class DeadLetterStats:
    """死信队列统计信息"""

    total_count: int  # 总数
    by_category: Dict[str, int]  # 按失败类型分组
    by_age: Dict[str, int]  # 按存在时间分组
    retry_success_rate: float  # 手动重试成功率
    avg_failure_count: float  # 平均失败次数


class ManualRetryResult(TypedDict):
    """手动重试结果结构（TypedDict，便于静态类型检查）"""

    total_requested: int
    successful_retries: int
    failed_retries: int
    success_task_ids: List[str]
    failed_tasks: List[Tuple[str, str]]
    retry_timestamp: str


class ManualRetryRequest(BaseModel):
    """手动重试请求"""

    task_ids: List[str]  # 要重试的任务ID列表
    retry_immediately: bool = False  # 是否立即重试
    override_policy: Optional[ConfigDict] = None  # 覆盖重试策略（采用统一ConfigDict类型）
    reason: str = "manual_retry"  # 重试原因


class DeadLetterQueryFilter(BaseModel):
    """死信队列查询过滤器"""

    failure_categories: Optional[List[str]] = None  # 失败类型过滤
    age_hours_min: Optional[int] = None  # 最小存在小时数
    age_hours_max: Optional[int] = None  # 最大存在小时数
    retry_count_min: Optional[int] = None  # 最小重试次数
    retry_count_max: Optional[int] = None  # 最大重试次数
    user_id: Optional[str] = None  # 用户ID过滤


class DeadLetterHandler:
    """死信队列处理器

    提供死信队列的完整管理功能：
    - 查询和过滤死信任务
    - 手动重试和批量操作
    - 统计分析和监控
    - 数据清理和归档
    """

    def __init__(self) -> None:
        self.retry_policy = get_retry_policy()

    def get_dead_letter_tasks(
        self,
        db_session: "Session",
        filters: Optional[DeadLetterQueryFilter] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Task], int]:
        """获取死信队列中的任务

        Args:
            db_session: 数据库会话
            filters: 查询过滤器
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            (任务列表, 总数量)
        """
        query = db_session.query(Task).filter(
            as_bool_clause(Task.status == TaskStatus.DEAD_LETTER.value)
        )

        # 应用过滤器
        if filters:
            if filters.failure_categories:
                query = query.filter(
                    as_bool_clause(
                        Task.failure_category.in_(filters.failure_categories)
                    )
                )

            if filters.user_id:
                query = query.filter(as_bool_clause(Task.user_id == filters.user_id))

            if filters.retry_count_min is not None:
                query = query.filter(
                    as_bool_clause(Task.retry_count >= filters.retry_count_min)
                )

            if filters.retry_count_max is not None:
                query = query.filter(
                    as_bool_clause(Task.retry_count <= filters.retry_count_max)
                )

            # 按存在时间过滤
            if filters.age_hours_min is not None or filters.age_hours_max is not None:
                now = datetime.utcnow()

                if filters.age_hours_min is not None:
                    min_time = now - timedelta(hours=filters.age_hours_min)
                    query = query.filter(
                        as_bool_clause(Task.dead_letter_at <= min_time)
                    )

                if filters.age_hours_max is not None:
                    max_time = now - timedelta(hours=filters.age_hours_max)
                    query = query.filter(
                        as_bool_clause(
                            and_(
                                Task.dead_letter_at <= min_time,
                                Task.dead_letter_at > max_time,
                            )
                        )
                    )

        # 获取总数
        total_count = query.count()

        # 分页查询
        tasks = (
            query.order_by(cast(Any, Task.dead_letter_at).desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        return tasks, total_count

    def manual_retry_tasks(
        self, db_session: "Session", retry_request: ManualRetryRequest
    ) -> ManualRetryResult:
        """手动重试死信队列中的任务

        Args:
            db_session: 数据库会话
            retry_request: 重试请求

        Returns:
            重试结果统计
        """
        success_tasks: List[str] = []
        failed_tasks: List[Tuple[str, str]] = []  # (task_id, error_reason)

        try:
            # 查询要重试的任务
            from uuid import UUID as UUIDType

            task_uuids = [
                UUIDType(tid) if isinstance(tid, str) else tid
                for tid in retry_request.task_ids
            ]

            tasks = (
                db_session.query(Task)
                .filter(
                    as_bool_clause(
                        and_(
                            Task.id.in_(task_uuids),
                            Task.status == TaskStatus.DEAD_LETTER.value,
                        )
                    )
                )
                .all()
            )

            if not tasks:
                raise ValueError("未找到可重试的死信任务")

            # 批量重试处理
            for task in tasks:
                try:
                    success = self._retry_single_task(task, retry_request, db_session)

                    if success:
                        success_tasks.append(str(task.id))
                    else:
                        failed_tasks.append((str(task.id), "重试条件不满足"))

                except Exception as e:
                    failed_tasks.append((str(task.id), str(e)))

            # 提交所有更改
            db_session.commit()

            # 记录重试操作
            self._log_manual_retry_operation(retry_request, success_tasks, failed_tasks)

            return {
                "total_requested": len(retry_request.task_ids),
                "successful_retries": len(success_tasks),
                "failed_retries": len(failed_tasks),
                "success_task_ids": success_tasks,
                "failed_tasks": failed_tasks,
                "retry_timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            db_session.rollback()
            raise RuntimeError(f"手动重试操作失败: {e}")

    def _retry_single_task(
        self, task: Task, retry_request: ManualRetryRequest, db_session: "Session"
    ) -> bool:
        """重试单个任务"""
        try:
            # 重置任务状态
            cast(Any, task).status = TaskStatus.PENDING.value
            cast(Any, task).retry_count = 0  # 重置重试次数，给任务新的机会
            cast(Any, task).error_message = None
            cast(Any, task).dead_letter_at = None
            cast(Any, task).last_retry_at = datetime.utcnow()

            # 如果需要立即重试，可以触发任务执行
            if retry_request.retry_immediately:
                self._trigger_immediate_execution(task)

            return True

        except Exception as e:
            # 单个任务失败不影响其他任务
            logging.getLogger(__name__).warning(
                f"重试任务失败", extra={"task_id": str(task.id), "error": str(e)}
            )
            return False

    def _trigger_immediate_execution(self, task: Task) -> None:
        """触发任务立即执行"""
        # TODO: 与Celery或其他任务调度系统集成
        # 例如：发送任务到执行队列
        # from ..tasks.analysis_tasks import execute_analysis_task
        # execute_analysis_task.delay(str(task.id))
        logging.getLogger(__name__).info("触发任务立即执行", extra={"task_id": str(task.id)})

    def get_dead_letter_statistics(self, db_session: "Session") -> DeadLetterStats:
        """获取死信队列统计信息"""
        # 总数查询
        total_count = (
            db_session.query(Task)
            .filter(as_bool_clause(Task.status == TaskStatus.DEAD_LETTER.value))
            .count()
        )

        # 按失败类型分组统计
        category_stats = (
            db_session.query(
                cast(Any, Task.failure_category),
                func.count(cast(Any, Task.id)).label("count"),
            )
            .filter(as_bool_clause(Task.status == TaskStatus.DEAD_LETTER.value))
            .group_by(Task.failure_category)
            .all()
        )

        by_category = {row[0] or "unknown": row[1] for row in category_stats}

        # 按存在时间分组统计
        now = datetime.utcnow()
        age_ranges = [
            ("0-1h", 0, 1),
            ("1-6h", 1, 6),
            ("6-24h", 6, 24),
            ("1-7d", 24, 24 * 7),
            ("7d+", 24 * 7, None),
        ]

        by_age = {}
        for label, min_hours, max_hours in age_ranges:
            query = db_session.query(Task).filter(
                as_bool_clause(Task.status == TaskStatus.DEAD_LETTER.value)
            )

            if min_hours is not None:
                min_time = now - timedelta(hours=min_hours)
                if max_hours is None:
                    query = query.filter(
                        as_bool_clause(Task.dead_letter_at <= min_time)
                    )
                else:
                    max_time = now - timedelta(hours=max_hours)
                    query = query.filter(
                        as_bool_clause(
                            and_(
                                Task.dead_letter_at <= min_time,
                                Task.dead_letter_at > max_time,
                            )
                        )
                    )

            by_age[label] = query.count()

        # 平均失败次数
        avg_failure_result = (
            db_session.query(func.avg(Task.retry_count).label("avg_failures"))
            .filter(as_bool_clause(Task.status == TaskStatus.DEAD_LETTER.value))
            .first()
        )

        avg_failure_count = (
            float(avg_failure_result[0]) if avg_failure_result[0] else 0.0
        )

        # TODO: 计算手动重试成功率（需要历史记录表）
        retry_success_rate = 0.0  # 暂时设为0，待实现历史记录跟踪

        return DeadLetterStats(
            total_count=total_count,
            by_category=by_category,
            by_age=by_age,
            retry_success_rate=retry_success_rate,
            avg_failure_count=avg_failure_count,
        )

    def cleanup_old_dead_letters(
        self, db_session: "Session", older_than_days: int = 30, dry_run: bool = True
    ) -> "CleanupResult":
        """清理旧的死信任务

        Args:
            db_session: 数据库会话
            older_than_days: 清理多少天前的记录
            dry_run: 是否为试运行（不实际删除）

        Returns:
            清理结果统计
        """
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)

        # 查询要清理的任务
        old_tasks_query = db_session.query(Task).filter(
            as_bool_clause(
                and_(
                    Task.status == TaskStatus.DEAD_LETTER.value,
                    Task.dead_letter_at <= cutoff_date,
                )
            )
        )

        tasks_to_delete = old_tasks_query.all()
        delete_count = len(tasks_to_delete)

        # 按失败类型统计
        category_counts: Dict[str, int] = {}
        for task in tasks_to_delete:
            category = task.failure_category or "unknown"
            category_counts[category] = category_counts.get(category, 0) + 1

        if not dry_run and delete_count > 0:
            # 实际删除
            try:
                old_tasks_query.delete(synchronize_session=False)
                db_session.commit()

                self._log_cleanup_operation(
                    delete_count, older_than_days, category_counts
                )

            except Exception as e:
                db_session.rollback()
                raise RuntimeError(f"清理死信任务失败: {e}")

        return {
            "total_deleted": delete_count,
            "cutoff_date": cutoff_date.isoformat(),
            "by_category": category_counts,
            "dry_run": dry_run,
            "cleanup_timestamp": datetime.utcnow().isoformat(),
        }

    def bulk_archive_dead_letters(
        self, db_session: "Session", filters: Optional[DeadLetterQueryFilter] = None
    ) -> NoReturn:
        """批量归档死信任务（状态保持，但标记为已归档）

        当前功能尚未实现。为了保证类型安全与调用时的显式失败，
        该函数会抛出 NotImplementedError。
        """
        raise NotImplementedError("bulk_archive_dead_letters 未实现：需要归档机制设计与表结构支持")

    def _log_manual_retry_operation(
        self,
        retry_request: ManualRetryRequest,
        success_tasks: List[str],
        failed_tasks: List[Tuple[str, str]],
    ) -> None:
        """记录手动重试操作日志"""
        import logging

        logger = logging.getLogger(__name__)

        logger.info(
            f"手动重试操作完成: "
            f"请求{len(retry_request.task_ids)}个任务, "
            f"成功{len(success_tasks)}个, "
            f"失败{len(failed_tasks)}个",
            extra={
                "operation": "manual_retry",
                "total_requested": len(retry_request.task_ids),
                "successful": len(success_tasks),
                "failed": len(failed_tasks),
                "reason": retry_request.reason,
            },
        )

    def _log_cleanup_operation(
        self, delete_count: int, older_than_days: int, category_counts: Dict[str, int]
    ) -> None:
        """记录清理操作日志"""
        import logging

        logger = logging.getLogger(__name__)

        logger.info(
            f"死信队列清理完成: " f"删除{delete_count}个超过{older_than_days}天的任务",
            extra={
                "operation": "cleanup_dead_letters",
                "deleted_count": delete_count,
                "retention_days": older_than_days,
                "by_category": category_counts,
            },
        )


# 全局死信处理器实例
dead_letter_handler = DeadLetterHandler()


def get_dead_letter_handler() -> DeadLetterHandler:
    """获取死信队列处理器实例"""
    return dead_letter_handler


class CleanupResult(TypedDict):
    """清理操作结果结构（TypedDict，便于静态类型检查）"""

    total_deleted: int
    cutoff_date: str
    by_category: Dict[str, int]
    dry_run: bool
    cleanup_timestamp: str
