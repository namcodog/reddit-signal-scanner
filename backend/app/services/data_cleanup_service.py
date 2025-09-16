"""
统一数据清理服务 - Reddit Signal Scanner (Linus架构合规版)
实现30天自动数据清理机制，防止数据库无限增长

基于Linus设计原则：
- 统一数据结构，消除特殊情况
- 策略模式消除if-else分支
- 职责分离，每个方法只做一件事
- 细粒度锁，支持不同清理类型并发
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional, Tuple, TypedDict, cast

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from ..core.cleanup_locks import CleanupCategory, acquire_cleanup_lock
from ..core.database import get_session_sync
from ..core.monitoring import monitor_cleanup_operation

logger = logging.getLogger(__name__)


class CleanupResult(TypedDict):
    """标准化清理结果数据结构 - 消除返回类型混乱"""

    category: str
    records_cleaned: int
    execution_time_seconds: float
    success: bool
    error_message: Optional[str]
    metadata: Mapping[str, Any]


class BatchCleanupResult(TypedDict):
    """批量清理结果数据结构"""

    total_records_cleaned: int
    execution_time_seconds: float
    success: bool
    breakdown: List[CleanupResult]
    database_stats: Mapping[str, Any]


# Linus原则：策略模式消除if-else分支
class CleanupStrategy:
    """抽象清理策略 - 消除cleanup_by_category的特殊情况"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def execute(self, **params: Any) -> CleanupResult:
        """执行清理策略的通用接口 - 带事务保护的版本"""
        start_time = time.time()
        category = self.get_category()

        # 获取细粒度锁 - Linus原则：最小锁粒度
        try:
            with acquire_cleanup_lock(category, timeout=30, task_info=params):
                # 开启数据库事务
                savepoint = self.db.begin_nested()  # 使用嵌套事务（保存点）

                try:
                    records_cleaned = self._execute_cleanup(**params)

                    # 验证清理结果的合理性
                    self._validate_cleanup_result(records_cleaned, category, params)

                    # 提交嵌套事务
                    savepoint.commit()

                    execution_time = time.time() - start_time

                    return CleanupResult(
                        category=category.value,
                        records_cleaned=records_cleaned,
                        execution_time_seconds=round(execution_time, 3),
                        success=True,
                        error_message=None,
                        metadata=self._get_metadata(**params),
                    )

                except (SQLAlchemyError, ValueError) as cleanup_error:
                    # 回滚嵌套事务
                    savepoint.rollback()
                    logger.error(f"清理策略 {category.value} 执行失败，已回滚: {cleanup_error}")

                    execution_time = time.time() - start_time

                    return CleanupResult(
                        category=category.value,
                        records_cleaned=0,
                        execution_time_seconds=round(execution_time, 3),
                        success=False,
                        error_message=str(cleanup_error),
                        metadata={},
                    )
                except (TypeError, KeyError, RuntimeError) as unexpected_error:
                    # 回滚嵌套事务
                    savepoint.rollback()
                    logger.exception(
                        "清理策略 %s 执行时出现未预期错误，已回滚",
                        category.value,
                    )

                    execution_time = time.time() - start_time

                    return CleanupResult(
                        category=category.value,
                        records_cleaned=0,
                        execution_time_seconds=round(execution_time, 3),
                        success=False,
                        error_message=str(unexpected_error),
                        metadata={},
                    )

        except TimeoutError as lock_error:
            execution_time = time.time() - start_time
            logger.error(f"无法获取清理锁 {category.value}: {lock_error}")

            return CleanupResult(
                category=category.value,
                records_cleaned=0,
                execution_time_seconds=round(execution_time, 3),
                success=False,
                error_message=str(lock_error),
                metadata={},
            )
        except (RuntimeError, OSError) as lock_error:
            execution_time = time.time() - start_time
            logger.error(f"获取清理锁时出现未预期错误 {category.value}: {lock_error}")

            return CleanupResult(
                category=category.value,
                records_cleaned=0,
                execution_time_seconds=round(execution_time, 3),
                success=False,
                error_message=str(lock_error),
                metadata={},
            )

    def get_category(self) -> CleanupCategory:
        """获取清理类别"""
        raise NotImplementedError

    def _execute_cleanup(self, **params: Any) -> int:
        """执行具体的清理逻辑"""
        raise NotImplementedError

    def _get_metadata(self, **params: Any) -> Mapping[str, Any]:
        """获取清理元数据"""
        return {}

    def get_dry_run_count(self, **params: Any) -> int:
        """获取试运行清理数量 - 抽象方法，子类必须实现"""
        raise NotImplementedError

    def _validate_cleanup_result(
        self, records_cleaned: int, category: CleanupCategory, params: Mapping[str, Any]
    ) -> None:
        """验证清理结果的合理性 - 防止意外大量删除"""
        max_limits = {
            CleanupCategory.COMPLETED_TASKS: 100000,  # 最多清理10万条完成任务
            CleanupCategory.FAILED_TASKS: 50000,  # 最多清理5万条失败任务
            CleanupCategory.ORPHAN_ANALYSES: 10000,  # 最多清理1万条孤儿分析
            CleanupCategory.EXPIRED_CACHE: 200000,  # 最多清理20万条缓存
            CleanupCategory.INACTIVE_USERS: 1000,  # 最多清理1000个非活跃用户
        }

        max_limit = max_limits.get(category, 1000)  # 默认限制1000条

        if records_cleaned > max_limit:
            raise ValueError(
                f"清理数量异常：{category.value} 清理了 {records_cleaned} 条记录，"
                f"超过安全限制 {max_limit} 条。可能存在参数错误或数据异常。"
            )


class CompletedTasksCleanupStrategy(CleanupStrategy):
    """完成任务清理策略"""

    def get_category(self) -> CleanupCategory:
        return CleanupCategory.COMPLETED_TASKS

    def _execute_cleanup(self, days_old: int = 30, **params: Any) -> int:
        # 参数验证 - Linus原则：早期验证，早期失败
        if days_old < 1 or days_old > 365:
            raise ValueError(f"完成任务保留天数无效: {days_old}，有效范围: [1, 365]")

        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        result = self.db.execute(
            text("SELECT cleanup_completed_tasks(:cutoff_date)"),
            {"cutoff_date": cutoff_date},
        )
        return result.scalar() or 0

    def _get_metadata(self, days_old: int = 30, **params: Any) -> Mapping[str, Any]:
        return {
            "days_old": days_old,
            "cutoff_date": (datetime.utcnow() - timedelta(days=days_old)).isoformat(),
        }

    def get_dry_run_count(self, days_old: int = 30, **params: Any) -> int:
        """获取完成任务试运行清理数量"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        result = self.db.execute(
            text("SELECT count_cleanup_completed_tasks(:cutoff_date)"),
            {"cutoff_date": cutoff_date},
        )
        return result.scalar() or 0


class FailedTasksCleanupStrategy(CleanupStrategy):
    """失败任务清理策略"""

    def get_category(self) -> CleanupCategory:
        return CleanupCategory.FAILED_TASKS

    def _execute_cleanup(self, days_old: int = 7, **params: Any) -> int:
        # 参数验证
        if days_old < 1 or days_old > 365:
            raise ValueError(f"失败任务保留天数无效: {days_old}，有效范围: [1, 365]")

        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        result = self.db.execute(
            text("SELECT cleanup_failed_tasks(:cutoff_date)"),
            {"cutoff_date": cutoff_date},
        )
        return result.scalar() or 0

    def _get_metadata(self, days_old: int = 7, **params: Any) -> Mapping[str, Any]:
        return {
            "days_old": days_old,
            "cutoff_date": (datetime.utcnow() - timedelta(days=days_old)).isoformat(),
        }

    def get_dry_run_count(self, days_old: int = 7, **params: Any) -> int:
        """获取失败任务试运行清理数量"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        result = self.db.execute(
            text("SELECT count_cleanup_failed_tasks(:cutoff_date)"),
            {"cutoff_date": cutoff_date},
        )
        return result.scalar() or 0


class OrphanAnalysesCleanupStrategy(CleanupStrategy):
    """孤儿分析清理策略"""

    def get_category(self) -> CleanupCategory:
        return CleanupCategory.ORPHAN_ANALYSES

    def _execute_cleanup(self, hours_old: float = 1.0, **params: Any) -> int:
        # 参数验证
        if hours_old < 0.1 or hours_old > 168:  # 最少6分钟，最多7天
            raise ValueError(f"孤儿分析保留小时数无效: {hours_old}，有效范围: [0.1, 168]")

        cutoff_time = datetime.utcnow() - timedelta(hours=hours_old)
        result = self.db.execute(
            text("SELECT cleanup_orphan_analyses(:cutoff_time)"),
            {"cutoff_time": cutoff_time},
        )
        return result.scalar() or 0

    def _get_metadata(self, hours_old: float = 1.0, **params: Any) -> Mapping[str, Any]:
        return {
            "hours_old": hours_old,
            "cutoff_time": (datetime.utcnow() - timedelta(hours=hours_old)).isoformat(),
        }

    def get_dry_run_count(self, hours_old: float = 1.0, **params: Any) -> int:
        """获取孤儿分析试运行清理数量"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_old)
        result = self.db.execute(
            text("SELECT count_cleanup_orphan_analyses(:cutoff_time)"),
            {"cutoff_time": cutoff_time},
        )
        return result.scalar() or 0


class ExpiredCacheCleanupStrategy(CleanupStrategy):
    """过期缓存清理策略"""

    def get_category(self) -> CleanupCategory:
        return CleanupCategory.EXPIRED_CACHE

    def _execute_cleanup(self, **params: Any) -> int:
        result = self.db.execute(text("SELECT cleanup_expired_community_cache()"))
        return result.scalar() or 0

    def _get_metadata(self, **params: Any) -> Mapping[str, Any]:
        return {"cleanup_time": datetime.utcnow().isoformat()}

    def get_dry_run_count(self, **params: Any) -> int:
        """获取过期缓存试运行清理数量"""
        result = self.db.execute(text("SELECT count_cleanup_expired_community_cache()"))
        return result.scalar() or 0


class InactiveUsersCleanupStrategy(CleanupStrategy):
    """非活跃用户清理策略"""

    def get_category(self) -> CleanupCategory:
        return CleanupCategory.INACTIVE_USERS

    def _execute_cleanup(self, days_old: int = 365, **params: Any) -> int:
        # 参数验证
        if days_old < 30 or days_old > 1095:  # 最少30天，最多3年
            raise ValueError(f"非活跃用户保留天数无效: {days_old}，有效范围: [30, 1095]")

        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        result = self.db.execute(
            text("SELECT cleanup_inactive_users(:cutoff_date)"),
            {"cutoff_date": cutoff_date},
        )
        return result.scalar() or 0

    def _get_metadata(self, days_old: int = 365, **params: Any) -> Mapping[str, Any]:
        return {
            "days_old": days_old,
            "cutoff_date": (datetime.utcnow() - timedelta(days=days_old)).isoformat(),
        }

    def get_dry_run_count(self, days_old: int = 365, **params: Any) -> int:
        """获取非活跃用户试运行清理数量"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        result = self.db.execute(
            text("SELECT count_cleanup_inactive_users(:cutoff_date)"),
            {"cutoff_date": cutoff_date},
        )
        return result.scalar() or 0


class DataCleanupService:
    """
    统一数据清理服务 - Linus架构合规版

    设计原则：
    1. 统一数据结构 - 所有操作返回标准CleanupResult
    2. 职责分离 - 每个方法只做一件事
    3. 消除特殊情况 - 通过多态消除if-else分支
    4. 细粒度锁 - 不同清理类型独立并发
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self._strategies = self._init_strategies()

    def _init_strategies(self) -> Dict[CleanupCategory, CleanupStrategy]:
        """初始化清理策略映射 - 消除if-else分支"""
        return {
            CleanupCategory.COMPLETED_TASKS: CompletedTasksCleanupStrategy(self.db),
            CleanupCategory.FAILED_TASKS: FailedTasksCleanupStrategy(self.db),
            CleanupCategory.ORPHAN_ANALYSES: OrphanAnalysesCleanupStrategy(self.db),
            CleanupCategory.EXPIRED_CACHE: ExpiredCacheCleanupStrategy(self.db),
            CleanupCategory.INACTIVE_USERS: InactiveUsersCleanupStrategy(self.db),
        }

    @monitor_cleanup_operation("single_category")
    def cleanup_by_category(self, category: str, **params: Any) -> CleanupResult:
        """
        按类别清理数据 - Linus重构版：消除特殊情况

        Args:
            category: 清理类别字符串
            **params: 清理参数（days_old, hours_old等）

        Returns:
            CleanupResult: 标准化清理结果
        """
        logger.info(f"执行分类清理: {category}")

        try:
            # 通过枚举消除字符串魔法值
            category_enum = CleanupCategory(category)

            # 通过策略模式消除if-else分支
            strategy = self._strategies.get(category_enum)
            if not strategy:
                raise ValueError(f"不支持的清理类别: {category}")

            # 执行清理策略
            result = strategy.execute(**params)

            # 策略模式已包含事务保护，这里只需要记录日志
            if result["success"]:
                logger.info(f"分类清理 {category} 完成: {result['records_cleaned']} 条记录")
            else:
                logger.error(f"分类清理 {category} 失败: {result['error_message']}")

            return result

        except ValueError as e:
            logger.error(f"不支持的清理类别 {category}: {e}")
            return CleanupResult(
                category=category,
                records_cleaned=0,
                execution_time_seconds=0,
                success=False,
                error_message=str(e),
                metadata={},
            )
        except SQLAlchemyError as e:
            logger.error(f"分类清理 {category} 数据库异常: {e}")
            # 策略模式已包含事务保护，这里不需要额外回滚
            return CleanupResult(
                category=category,
                records_cleaned=0,
                execution_time_seconds=0,
                success=False,
                error_message=str(e),
                metadata={},
            )
        except (TypeError, KeyError, RuntimeError) as e:
            logger.exception(f"分类清理 {category} 执行出现未预期异常: {e}")
            return CleanupResult(
                category=category,
                records_cleaned=0,
                execution_time_seconds=0,
                success=False,
                error_message=str(e),
                metadata={},
            )

    @monitor_cleanup_operation("full_batch")
    def execute_full_cleanup(
        self,
        completed_task_days: int = 30,
        failed_task_days: int = 7,
        orphan_analysis_hours: float = 1.0,
        inactive_user_days: int = 365,
        dry_run: bool = False,
    ) -> BatchCleanupResult:
        """
        执行完整数据清理 - Linus重构版：拆分大方法

        Args:
            completed_task_days: 完成任务保留天数
            failed_task_days: 失败任务保留天数
            orphan_analysis_hours: 孤儿分析记录保留小时数
            inactive_user_days: 非活跃用户保留天数
            dry_run: 是否试运行（只统计不删除）

        Returns:
            BatchCleanupResult: 标准化批量清理结果
        """
        start_time = time.time()
        logger.info(f"开始执行完整数据清理 - 试运行: {dry_run}")

        # 小函数1：验证参数
        self._validate_parameters(
            completed_task_days,
            failed_task_days,
            orphan_analysis_hours,
            inactive_user_days,
        )

        # 小函数2：执行各类清理
        cleanup_results = self._execute_all_cleanups(
            completed_task_days,
            failed_task_days,
            orphan_analysis_hours,
            inactive_user_days,
            dry_run,
        )

        # 小函数3：生成最终结果
        return self._build_batch_result(cleanup_results, start_time)

    def _execute_all_cleanups(
        self,
        completed_days: int,
        failed_days: int,
        orphan_hours: float,
        inactive_days: int,
        dry_run: bool,
    ) -> List[CleanupResult]:
        """执行所有清理任务 - 小函数"""
        results = []

        # 使用策略模式批量执行清理
        cleanup_params: List[Tuple[CleanupCategory, Mapping[str, Any]]] = [
            (CleanupCategory.COMPLETED_TASKS, {"days_old": completed_days}),
            (CleanupCategory.FAILED_TASKS, {"days_old": failed_days}),
            (CleanupCategory.ORPHAN_ANALYSES, {"hours_old": orphan_hours}),
            (CleanupCategory.EXPIRED_CACHE, {}),
            (CleanupCategory.INACTIVE_USERS, {"days_old": inactive_days}),
        ]

        # 使用事务保护批量清理
        savepoint = self.db.begin_nested()  # 嵌套事务保护整个批量操作

        try:
            for category, params in cleanup_params:
                if dry_run:
                    # 试运行模式：使用数据库存储过程预览
                    result = self._execute_dry_run_cleanup(category, params)
                else:
                    # 实际执行模式：使用策略模式（已包含单独的事务保护）
                    result = self._strategies[category].execute(**params)

                results.append(result)

                # 如果某个清理失败且不是试运行，立即停止
                if not dry_run and not result["success"]:
                    logger.error(f"清理类别 {category.value} 失败，停止后续清理")
                    break

            # 检查整体结果
            failed_count = sum(1 for r in results if not r["success"])
            if failed_count > 0 and not dry_run:
                raise RuntimeError(f"批量清理中有 {failed_count} 个类别失败")

            # 提交整个批量操作
            if not dry_run:
                savepoint.commit()
                logger.info("批量清理事务提交成功")

        except (SQLAlchemyError, RuntimeError) as e:
            # 回滚整个批量操作
            if not dry_run:
                savepoint.rollback()
                logger.error("批量清理失败，已回滚所有操作: %s", e)

                # 将所有结果标记为失败
                for result in results:
                    if result["success"]:
                        result["success"] = False
                        result["error_message"] = f"批量操作回滚: {e}"

            raise
        except (TypeError, ValueError) as e:
            if not dry_run:
                savepoint.rollback()
                logger.exception("批量清理出现参数/类型异常，已回滚所有操作")
            raise

        return results

    def _execute_dry_run_cleanup(
        self, category: CleanupCategory, params: Mapping[str, Any]
    ) -> CleanupResult:
        """执行试运行清理 - Linus重构版：策略模式消除if-elif链"""
        start_time = time.time()

        try:
            # 策略模式 - 消除47行if-elif链
            strategy = self._strategies.get(category)
            if not strategy:
                raise ValueError(f"不支持的清理类别: {category}")

            # 调用策略的dry run方法 - 统一接口
            records_to_clean = strategy.get_dry_run_count(**params)
            execution_time = time.time() - start_time

            return CleanupResult(
                category=category.value,
                records_cleaned=records_to_clean,
                execution_time_seconds=round(execution_time, 3),
                success=True,
                error_message=None,
                metadata={"dry_run": True, **params},
            )

        except SQLAlchemyError as e:
            execution_time = time.time() - start_time
            return CleanupResult(
                category=category.value,
                records_cleaned=0,
                execution_time_seconds=round(execution_time, 3),
                success=False,
                error_message=str(e),
                metadata={"dry_run": True, **params},
            )
        except ValueError as e:
            execution_time = time.time() - start_time
            return CleanupResult(
                category=category.value,
                records_cleaned=0,
                execution_time_seconds=round(execution_time, 3),
                success=False,
                error_message=str(e),
                metadata={"dry_run": True, **params},
            )
        except (TypeError, KeyError) as e:
            execution_time = time.time() - start_time
            return CleanupResult(
                category=category.value,
                records_cleaned=0,
                execution_time_seconds=round(execution_time, 3),
                success=False,
                error_message=str(e),
                metadata={"dry_run": True, **params},
            )

    def _build_batch_result(
        self, cleanup_results: List[CleanupResult], start_time: float
    ) -> BatchCleanupResult:
        """构建批量清理结果 - 小函数"""
        total_records = sum(
            result["records_cleaned"] for result in cleanup_results if result["success"]
        )
        execution_time = time.time() - start_time
        overall_success = all(result["success"] for result in cleanup_results)

        return BatchCleanupResult(
            total_records_cleaned=total_records,
            execution_time_seconds=round(execution_time, 2),
            success=overall_success,
            breakdown=cleanup_results,
            database_stats=self._get_database_stats(),
        )

    def _validate_parameters(
        self,
        completed_days: int,
        failed_days: int,
        orphan_hours: float,
        inactive_days: int,
    ) -> None:
        """参数验证 - 小函数"""
        validators = [
            (completed_days, 1, 365, "完成任务保留天数"),
            (failed_days, 1, 365, "失败任务保留天数"),
            (orphan_hours, 0.1, 168, "孤儿分析保留小时数"),
            (inactive_days, 30, 1095, "非活跃用户保留天数"),
        ]

        for value, min_val, max_val, name in validators:
            if not (min_val <= value <= max_val):
                raise ValueError(f"{name}无效: {value}, 范围: [{min_val}, {max_val}]")

    def get_cleanup_preview(self) -> BatchCleanupResult:
        """
        预览清理效果 - 不实际执行删除

        Returns:
            BatchCleanupResult: 将要清理的数据统计
        """
        logger.info("生成数据清理预览")

        try:
            # 调用完整清理的试运行模式
            result = self.execute_full_cleanup(dry_run=True)
            return cast(BatchCleanupResult, result)

        except SQLAlchemyError as e:
            logger.error(f"清理预览失败（数据库异常）: {e}")
            raise

    def get_cleanup_history(self, days: int = 30) -> List[Mapping[str, Any]]:
        """
        获取清理历史记录

        Args:
            days: 查询天数

        Returns:
            List: 清理历史记录
        """
        try:
            result = self.db.execute(
                text(
                    """
                    SELECT
                        executed_at,
                        total_records_cleaned,
                        breakdown,
                        duration_seconds,
                        success,
                        error_message
                    FROM cleanup_logs
                    WHERE executed_at >= CURRENT_TIMESTAMP - INTERVAL :interval_days
                    ORDER BY executed_at DESC
                    LIMIT 100
                """
                ),
                {"interval_days": f"{days} days"},
            )

            history: List[Mapping[str, Any]] = []
            for row in result:
                history.append(
                    {
                        "executed_at": row[0],
                        "total_records_cleaned": row[1],
                        "breakdown": row[2],
                        "duration_seconds": row[3],
                        "success": row[4],
                        "error_message": row[5],
                    }
                )

            return history

        except SQLAlchemyError as e:
            logger.error("获取清理历史失败（数据库异常）: %s", e)
            raise

    def get_cleanup_statistics(self) -> Mapping[str, Any]:
        """
        获取清理统计信息

        Returns:
            Dict: 清理统计数据
        """
        try:
            result = self.db.execute(
                text(
                    """
                    SELECT
                        cleanup_date,
                        cleanup_runs,
                        avg_records_cleaned,
                        max_records_cleaned,
                        avg_duration_seconds,
                        success_rate_percent
                    FROM cleanup_stats
                    ORDER BY cleanup_date DESC
                    LIMIT 30
                """
                )
            )

            stats: List[Mapping[str, Any]] = []
            for row in result:
                stats.append(
                    {
                        "date": row[0].strftime("%Y-%m-%d") if row[0] else None,
                        "runs": row[1],
                        "avg_cleaned": round(float(row[2]), 1) if row[2] else 0,
                        "max_cleaned": row[3],
                        "avg_duration": round(float(row[4]), 1) if row[4] else 0,
                        "success_rate": round(float(row[5]), 1) if row[5] else 0,
                    }
                )

            return {
                "daily_stats": stats,
                "summary": self._calculate_summary_stats(stats),
            }

        except SQLAlchemyError as e:
            logger.error("获取清理统计失败（数据库异常）: %s", e)
            raise

    def _get_database_stats(self) -> Mapping[str, Any]:
        """获取数据库统计信息"""
        try:
            stats = {}

            # 获取各表的记录数
            table_counts = self.db.execute(
                text(
                    """
                    SELECT
                        'tasks' as table_name, COUNT(*) as record_count FROM tasks
                    UNION ALL
                    SELECT 'analyses', COUNT(*) FROM analyses
                    UNION ALL
                    SELECT 'reports', COUNT(*) FROM reports
                    UNION ALL
                    SELECT 'community_cache', COUNT(*) FROM community_cache
                    UNION ALL
                    SELECT 'users', COUNT(*) FROM users
                """
                )
            )

            for row in table_counts:
                stats[f"{row[0]}_count"] = row[1]

            # 获取数据库大小（如果可用）
            try:
                db_size = self.db.execute(
                    text("SELECT pg_database_size(current_database())")
                ).scalar()

                if db_size:
                    stats["database_size_bytes"] = db_size
                    stats["database_size_mb"] = round(db_size / 1024 / 1024, 2)

            except SQLAlchemyError as size_err:
                logger.debug("获取数据库大小失败，跳过: %s", size_err)

            return stats

        except SQLAlchemyError as e:
            logger.warning(f"获取数据库统计失败（数据库异常）: {e}")
            return {}

    def _record_cleanup_failure(self, error_message: str, dry_run: bool) -> None:
        """记录清理失败日志"""
        try:
            if not dry_run:  # 只有实际执行时才记录失败日志
                self.db.execute(
                    text(
                        """
                        INSERT INTO cleanup_logs
                        (executed_at, total_records_cleaned, breakdown, success,
                         error_message)
                        VALUES (:executed_at, 0, :breakdown, false, :error_message)
                    """
                    ),
                    {
                        "executed_at": datetime.utcnow(),
                        "breakdown": json.dumps({"error": "cleanup_failed"}),
                        "error_message": error_message[:1000],  # 限制错误消息长度
                    },
                )
                self.db.commit()
        except SQLAlchemyError as e:
            logger.error(f"记录失败日志失败（数据库异常）: {e}")

    def _calculate_summary_stats(
        self, daily_stats: List[Mapping[str, Any]]
    ) -> Mapping[str, Any]:
        """计算汇总统计"""
        if not daily_stats:
            return {}

        total_runs = sum(stat["runs"] for stat in daily_stats)
        avg_success_rate = sum(stat["success_rate"] for stat in daily_stats) / len(
            daily_stats
        )

        return {
            "total_cleanup_runs": total_runs,
            "avg_success_rate": round(avg_success_rate, 1),
            "days_covered": len(daily_stats),
            "last_cleanup": daily_stats[0]["date"] if daily_stats else None,
        }


class CleanupManager:
    """清理管理器 - 提供便捷的清理操作接口"""

    def __init__(self) -> None:
        self.db: Optional[Session] = None
        self.service: Optional["DataCleanupService"] = None

    def __enter__(self) -> "DataCleanupService":
        # 使用同步会话，避免 AsyncSession.query 反模式
        self.db = get_session_sync()
        self.service = DataCleanupService(self.db)
        return self.service

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.db:
            try:
                self.db.close()
            except (RuntimeError, OSError) as close_err:
                logger.debug("关闭数据库会话失败，已忽略: %s", close_err)


# 便捷函数
def execute_cleanup(dry_run: bool = False, **kwargs: Any) -> BatchCleanupResult:
    """执行数据清理的便捷函数"""
    with CleanupManager() as cleanup_service:
        return cast(
            BatchCleanupResult,
            cleanup_service.execute_full_cleanup(dry_run=dry_run, **kwargs),
        )


def get_cleanup_preview() -> BatchCleanupResult:
    """获取清理预览的便捷函数"""
    with CleanupManager() as cleanup_service:
        return cleanup_service.get_cleanup_preview()


def get_cleanup_history(days: int = 30) -> List[Mapping[str, Any]]:
    """获取清理历史的便捷函数"""
    with CleanupManager() as cleanup_service:
        return cleanup_service.get_cleanup_history(days)


def get_cleanup_stats() -> Mapping[str, Any]:
    """获取清理统计的便捷函数"""
    with CleanupManager() as cleanup_service:
        return cleanup_service.get_cleanup_statistics()


# 导出接口
__all__ = [
    "DataCleanupService",
    "CleanupManager",
    "execute_cleanup",
    "get_cleanup_preview",
    "get_cleanup_history",
    "get_cleanup_stats",
    "CleanupResult",
    "BatchCleanupResult",
    "CleanupCategory",
]
