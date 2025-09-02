"""
统一数据清理服务 - Reddit Signal Scanner
实现30天自动数据清理机制，防止数据库无限增长

基于Linus设计原则：
- 数据库执行清理，应用管理策略
- 简单的接口，复杂的逻辑在SQL层
- 完整的错误处理和日志记录
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from sqlalchemy.exc import SQLAlchemyError
import logging
import time
import json

from ..core.database import get_db
from ..core.config import settings

logger = logging.getLogger(__name__)


class DataCleanupService:
    """
    统一数据清理服务 - 生产级实现

    功能：
    - 清理完成的任务（30天）
    - 清理失败的任务（7天）
    - 清理孤儿分析记录（1小时）
    - 清理过期缓存（TTL驱动）
    - 清理非活跃用户（365天，软删除）
    """

    def __init__(self, db: Session):
        self.db = db
        self.cleanup_stats = {}
        self.start_time = None

    def execute_full_cleanup(
        self,
        completed_task_days: int = 30,
        failed_task_days: int = 7,
        orphan_analysis_hours: float = 1.0,
        inactive_user_days: int = 365,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        执行完整数据清理 - 主要入口点

        Args:
            completed_task_days: 完成任务保留天数
            failed_task_days: 失败任务保留天数
            orphan_analysis_hours: 孤儿分析记录保留小时数
            inactive_user_days: 非活跃用户保留天数
            dry_run: 是否试运行（只统计不删除）

        Returns:
            Dict: 清理结果统计
        """
        self.start_time = time.time()

        logger.info(f"开始执行数据清理任务 - 试运行: {dry_run}")

        try:
            # 参数验证
            self._validate_cleanup_parameters(
                completed_task_days,
                failed_task_days,
                orphan_analysis_hours,
                inactive_user_days,
            )

            # 使用数据库存储过程执行清理
            result = self.db.execute(
                text(
                    """
                    SELECT execute_data_cleanup(
                        :completed_days, :failed_days, :orphan_hours, 
                        :inactive_days, :dry_run
                    )
                """
                ),
                {
                    "completed_days": completed_task_days,
                    "failed_days": failed_task_days,
                    "orphan_hours": orphan_analysis_hours,
                    "inactive_days": inactive_user_days,
                    "dry_run": dry_run,
                },
            )

            cleanup_results = result.scalar()

            if not dry_run:
                self.db.commit()

            # 转换JSON结果为Python字典
            if isinstance(cleanup_results, str):
                cleanup_results = json.loads(cleanup_results)

            # 添加执行时间
            execution_time = time.time() - self.start_time
            cleanup_results["execution_time_seconds"] = round(execution_time, 2)

            logger.info(f"数据清理完成: {cleanup_results}")
            return cleanup_results

        except SQLAlchemyError as e:
            logger.error(f"数据库清理失败: {e}")
            self.db.rollback()

            # 记录失败日志
            self._record_cleanup_failure(str(e), dry_run)
            raise

        except Exception as e:
            logger.error(f"数据清理异常: {e}")
            self.db.rollback()
            raise

    def get_cleanup_preview(self) -> Dict[str, Any]:
        """
        预览清理效果 - 不实际执行删除

        Returns:
            Dict: 将要清理的数据统计
        """
        logger.info("生成数据清理预览")

        try:
            # 调用存储过程进行试运行
            result = self.execute_full_cleanup(dry_run=True)

            # 添加数据库大小信息
            db_stats = self._get_database_stats()
            result.update(db_stats)

            return result

        except Exception as e:
            logger.error(f"清理预览失败: {e}")
            raise

    def cleanup_by_category(
        self,
        category: str,
        days_old: Optional[int] = None,
        hours_old: Optional[float] = None,
    ) -> int:
        """
        按类别清理数据

        Args:
            category: 清理类别 (completed_tasks, failed_tasks, orphan_analyses, etc.)
            days_old: 保留天数
            hours_old: 保留小时数

        Returns:
            int: 清理的记录数
        """
        logger.info(f"执行分类清理: {category}")

        try:
            if category == "completed_tasks":
                days_old = days_old or 30
                cutoff_date = datetime.utcnow() - timedelta(days=days_old)
                result = self.db.execute(
                    text("SELECT cleanup_completed_tasks(:cutoff_date)"),
                    {"cutoff_date": cutoff_date},
                )

            elif category == "failed_tasks":
                days_old = days_old or 7
                cutoff_date = datetime.utcnow() - timedelta(days=days_old)
                result = self.db.execute(
                    text("SELECT cleanup_failed_tasks(:cutoff_date)"),
                    {"cutoff_date": cutoff_date},
                )

            elif category == "orphan_analyses":
                hours_old = hours_old or 1.0
                cutoff_time = datetime.utcnow() - timedelta(hours=hours_old)
                result = self.db.execute(
                    text("SELECT cleanup_orphan_analyses(:cutoff_time)"),
                    {"cutoff_time": cutoff_time},
                )

            elif category == "expired_cache":
                result = self.db.execute(
                    text("SELECT cleanup_expired_community_cache()")
                )

            elif category == "inactive_users":
                days_old = days_old or 365
                cutoff_date = datetime.utcnow() - timedelta(days=days_old)
                result = self.db.execute(
                    text("SELECT cleanup_inactive_users(:cutoff_date)"),
                    {"cutoff_date": cutoff_date},
                )

            else:
                raise ValueError(f"不支持的清理类别: {category}")

            deleted_count = result.scalar()
            self.db.commit()

            logger.info(f"分类清理 {category} 完成: {deleted_count} 条记录")
            return deleted_count

        except Exception as e:
            logger.error(f"分类清理 {category} 失败: {e}")
            self.db.rollback()
            raise

    def get_cleanup_history(self, days: int = 30) -> List[Dict[str, Any]]:
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

            history = []
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

        except Exception as e:
            logger.error(f"获取清理历史失败: {e}")
            raise

    def get_cleanup_statistics(self) -> Dict[str, Any]:
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

            stats = []
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

        except Exception as e:
            logger.error(f"获取清理统计失败: {e}")
            raise

    def _validate_cleanup_parameters(
        self,
        completed_days: int,
        failed_days: int,
        orphan_hours: float,
        inactive_days: int,
    ):
        """验证清理参数"""
        if completed_days < 1 or completed_days > 365:
            raise ValueError(f"完成任务保留天数无效: {completed_days}")

        if failed_days < 1 or failed_days > 365:
            raise ValueError(f"失败任务保留天数无效: {failed_days}")

        if orphan_hours < 0.1 or orphan_hours > 168:  # 最多7天
            raise ValueError(f"孤儿分析保留小时数无效: {orphan_hours}")

        if inactive_days < 30 or inactive_days > 1095:  # 最少30天，最多3年
            raise ValueError(f"非活跃用户保留天数无效: {inactive_days}")

    def _get_database_stats(self) -> Dict[str, Any]:
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

            except Exception:
                # 如果获取数据库大小失败，跳过
                pass

            return stats

        except Exception as e:
            logger.warning(f"获取数据库统计失败: {e}")
            return {}

    def _record_cleanup_failure(self, error_message: str, dry_run: bool):
        """记录清理失败日志"""
        try:
            if not dry_run:  # 只有实际执行时才记录失败日志
                self.db.execute(
                    text(
                        """
                        INSERT INTO cleanup_logs 
                        (executed_at, total_records_cleaned, breakdown, success, error_message)
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
        except Exception as e:
            logger.error(f"记录失败日志失败: {e}")

    def _calculate_summary_stats(self, daily_stats: List[Dict]) -> Dict[str, Any]:
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

    def __init__(self):
        self.db = None

    def __enter__(self):
        self.db = next(get_db())
        self.service = DataCleanupService(self.db)
        return self.service

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()


# 便捷函数
def execute_cleanup(dry_run: bool = False, **kwargs) -> Dict[str, Any]:
    """执行数据清理的便捷函数"""
    with CleanupManager() as cleanup_service:
        return cleanup_service.execute_full_cleanup(dry_run=dry_run, **kwargs)


def get_cleanup_preview() -> Dict[str, Any]:
    """获取清理预览的便捷函数"""
    with CleanupManager() as cleanup_service:
        return cleanup_service.get_cleanup_preview()


def get_cleanup_history(days: int = 30) -> List[Dict[str, Any]]:
    """获取清理历史的便捷函数"""
    with CleanupManager() as cleanup_service:
        return cleanup_service.get_cleanup_history(days)


def get_cleanup_stats() -> Dict[str, Any]:
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
]
