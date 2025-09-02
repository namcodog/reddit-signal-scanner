"""
Reddit Signal Scanner - 任务状态查询服务

Linus原则应用：
- 数据结构决定一切：Task ORM → TaskInfo API 的清晰转换
- 消除特殊情况：统一的状态映射和进度计算
- 简单性：一个服务类解决所有状态查询需求
- 错误处理：优雅降级，不崩溃
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.models import TaskInfo, TaskStatus as ApiTaskStatus
from ..models.task import TaskStatus as DbTaskStatus

logger = logging.getLogger(__name__)


class TaskStatusService:
    """任务状态查询服务 - 数据库到API的桥梁

    核心功能：
    1. 数据库Task模型到API TaskInfo模型的转换
    2. 状态映射：processing -> running
    3. 进度计算：基于运行时间的智能估算
    4. 批量查询优化：减少数据库往返
    5. 错误处理：连接失败时的优雅降级
    """

    # Linus原则：消除特殊情况的状态映射字典
    DB_TO_API_STATUS_MAP = {
        DbTaskStatus.PENDING.value: ApiTaskStatus.PENDING,
        DbTaskStatus.PROCESSING.value: ApiTaskStatus.RUNNING,  # 关键映射
        DbTaskStatus.COMPLETED.value: ApiTaskStatus.COMPLETED,
        DbTaskStatus.FAILED.value: ApiTaskStatus.FAILED,
    }

    def __init__(self, db: AsyncSession):
        """初始化服务

        Args:
            db: 异步数据库会话
        """
        self.db = db

    async def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """查询单个任务状态

        Args:
            task_id: 任务ID（支持UUID字符串格式）

        Returns:
            TaskInfo: 任务信息，不存在时返回None

        Raises:
            无异常抛出，遇到错误返回None并记录日志
        """
        try:
            # 参数验证
            if not task_id or len(task_id.strip()) < 4:
                logger.warning(f"无效的任务ID格式: {task_id}")
                return None

            # 尝试转换为UUID
            try:
                task_uuid = UUID(task_id)
            except ValueError:
                logger.warning(f"任务ID不是有效的UUID格式: {task_id}")
                return None

            # 查询任务
            query = text(
                """
                SELECT id, user_id, status, created_at, updated_at,
                       completed_at, error_message
                FROM tasks
                WHERE id = :task_id
                """
            )

            result = await self.db.execute(query, {"task_id": task_uuid})
            row = result.fetchone()

            if not row:
                logger.info(f"任务不存在: {task_id}")
                return None

            # 转换为TaskInfo
            return self._convert_db_row_to_task_info(row, task_id)

        except SQLAlchemyError as e:
            logger.error(f"数据库查询失败 - task_id: {task_id}, error: {e}")
            return None
        except Exception as e:
            logger.error(f"任务状态查询异常 - task_id: {task_id}, error: {e}")
            return None

    async def get_multiple_tasks_status(
        self, task_ids: List[str], limit: int = 10
    ) -> Dict[str, Union[TaskInfo, Dict[str, str]]]:
        """批量查询任务状态

        Args:
            task_ids: 任务ID列表
            limit: 最大查询数量限制

        Returns:
            Dict[str, Union[TaskInfo, Dict[str, str]]]:
            成功时返回TaskInfo，失败时返回错误信息字典
        """
        results: Dict[str, Union[TaskInfo, Dict[str, str]]] = {}

        if not task_ids:
            return results

        # 限制查询数量
        limited_ids = task_ids[:limit]

        # 验证UUID格式
        valid_uuids = []
        id_mapping = {}  # UUID -> 原始字符串的映射

        for task_id in limited_ids:
            if not task_id or len(task_id.strip()) < 4:
                results[task_id] = {"error": "无效的任务ID格式"}
                continue

            try:
                task_uuid = UUID(task_id)
                valid_uuids.append(task_uuid)
                id_mapping[task_uuid] = task_id
            except ValueError:
                results[task_id] = {"error": "任务ID不是有效的UUID格式"}
                continue

        if not valid_uuids:
            return results

        try:
            # 批量查询
            query = text(
                """
                SELECT id, user_id, status, created_at, updated_at,
                       completed_at, error_message
                FROM tasks
                WHERE id = ANY(:task_ids)
                """
            )

            result = await self.db.execute(query, {"task_ids": valid_uuids})
            rows = result.fetchall()

            # 处理查询结果
            found_ids = set()
            for row in rows:
                task_uuid = row.id
                original_id = id_mapping[task_uuid]
                found_ids.add(task_uuid)

                task_info = self._convert_db_row_to_task_info(row, original_id)
                if task_info:
                    results[original_id] = task_info
                else:
                    results[original_id] = {"error": "数据转换失败"}

            # 处理未找到的任务
            for task_uuid in valid_uuids:
                if task_uuid not in found_ids:
                    original_id = id_mapping[task_uuid]
                    results[original_id] = {"error": "任务不存在"}

        except SQLAlchemyError as e:
            logger.error(f"批量查询失败: {e}")
            # 为所有剩余的有效ID返回数据库错误
            for task_uuid, original_id in id_mapping.items():
                if original_id not in results:
                    results[original_id] = {"error": "数据库查询失败"}
        except Exception as e:
            logger.error(f"批量查询异常: {e}")
            for task_uuid, original_id in id_mapping.items():
                if original_id not in results:
                    results[original_id] = {"error": "查询异常"}

        return results

    def _convert_db_row_to_task_info(
        self, row: Any, task_id: str
    ) -> Optional[TaskInfo]:
        """数据库行转换为TaskInfo模型

        Args:
            row: 数据库查询结果行
            task_id: 原始任务ID字符串

        Returns:
            TaskInfo: 转换后的任务信息，失败时返回None
        """
        try:
            # 状态映射
            db_status = row.status
            api_status = self.DB_TO_API_STATUS_MAP.get(db_status)

            if api_status is None:
                logger.warning(f"未知的数据库状态: {db_status}")
                api_status = ApiTaskStatus.FAILED  # 默认为失败状态

            # 进度计算
            progress = self._calculate_progress(
                db_status, row.created_at, row.updated_at, row.completed_at
            )

            # 时间格式化
            created_at = self._format_timestamp(row.created_at)
            updated_at = self._format_timestamp(row.updated_at)

            # 预估完成时间计算
            estimated_completion = None
            if api_status == ApiTaskStatus.RUNNING:
                estimated_completion = self._calculate_estimated_completion(
                    row.created_at, row.updated_at
                )

            return TaskInfo(
                task_id=task_id,
                status=api_status,
                progress=progress,
                created_at=created_at,
                updated_at=updated_at,
                estimated_completion=estimated_completion,
                error_message=row.error_message if row.error_message else None,
            )

        except Exception as e:
            logger.error(f"数据转换失败 - task_id: {task_id}, error: {e}")
            return None

    def _calculate_progress(
        self,
        status: str,
        created_at: datetime,
        updated_at: datetime,
        completed_at: Optional[datetime],
    ) -> int:
        """计算任务进度百分比

        Linus原则：简单的线性计算，无特殊情况

        Args:
            status: 任务状态
            created_at: 创建时间
            updated_at: 更新时间
            completed_at: 完成时间

        Returns:
            int: 进度百分比 (0-100)
        """
        try:
            if status == DbTaskStatus.PENDING.value:
                return 0
            elif status == DbTaskStatus.COMPLETED.value:
                return 100
            elif status == DbTaskStatus.FAILED.value:
                return 0
            elif status == DbTaskStatus.PROCESSING.value:
                # 基于运行时间的线性估算，使用配置化的时长
                from ..core.fallback import get_fallback_config

                config = get_fallback_config()
                max_duration_seconds = config.estimated_duration_seconds

                current_time = datetime.now(timezone.utc)
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)

                runtime_seconds = (current_time - updated_at).total_seconds()
                # 基于配置的任务时长计算进度，最高到90%，为完成状态留空间
                progress = min(int(runtime_seconds / max_duration_seconds * 90), 90)
                return max(progress, 5)  # 最少5%，表示已开始处理
            else:
                return 0

        except Exception as e:
            logger.warning(f"进度计算失败: {e}")
            return 0

    def _calculate_estimated_completion(
        self, created_at: datetime, updated_at: datetime
    ) -> Optional[str]:
        """计算预估完成时间

        Args:
            created_at: 创建时间
            updated_at: 更新时间（开始处理时间）

        Returns:
            str: ISO格式的预估完成时间，计算失败返回None
        """
        try:
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)

            # 使用配置化的任务预估时长
            from ..core.fallback import get_fallback_config

            config = get_fallback_config()
            estimated_duration_seconds = config.estimated_duration_seconds
            from datetime import timedelta

            estimated_time = updated_at.replace(microsecond=0) + timedelta(
                seconds=estimated_duration_seconds
            )

            return estimated_time.isoformat().replace("+00:00", "Z")

        except Exception as e:
            logger.warning(f"预估完成时间计算失败: {e}")
            return None

    def _format_timestamp(self, timestamp: datetime) -> str:
        """格式化时间戳为ISO格式

        Args:
            timestamp: 数据库时间戳

        Returns:
            str: ISO格式时间字符串
        """
        try:
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            return timestamp.isoformat().replace("+00:00", "Z")
        except Exception:
            return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    async def get_user_tasks_summary(self, user_id: str) -> Dict[str, int]:
        """获取用户任务状态统计

        Args:
            user_id: 用户ID

        Returns:
            Dict[str, int]: 各状态的任务数量统计
        """
        try:
            user_uuid = UUID(user_id)

            query = text(
                """
                SELECT status, COUNT(*) as task_count
                FROM tasks
                WHERE user_id = :user_id
                GROUP BY status
            """
            )

            result = await self.db.execute(query, {"user_id": user_uuid})
            rows = result.fetchall()

            # 映射到API状态
            summary = {status.value: 0 for status in ApiTaskStatus}

            for row in rows:
                db_status = row.status
                api_status = self.DB_TO_API_STATUS_MAP.get(db_status)
                if api_status:
                    current_count = summary[api_status.value]
                    new_count = int(row.task_count)  # 使用task_count字段
                    summary[api_status.value] = current_count + new_count

            return summary

        except Exception as e:
            logger.error(f"用户任务统计失败 - user_id: {user_id}, error: {e}")
            return {status.value: 0 for status in ApiTaskStatus}


# 便捷工厂函数
def create_task_status_service(db: AsyncSession) -> TaskStatusService:
    """创建任务状态服务实例

    Args:
        db: 数据库会话

    Returns:
        TaskStatusService: 服务实例
    """
    return TaskStatusService(db)
