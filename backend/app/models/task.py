"""
Reddit Signal Scanner - 任务模型

Linus设计原则: "数据结构决定一切 + 消除特殊情况"
- 简单状态机：4个状态，无中间态，无特殊情况
- 约束下沉：业务规则在数据库层保证，ORM层零负担
- 索引优化：基于实际查询模式，支持多租户高效查询
"""

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Column,
    String,
    TEXT,
    TIMESTAMP,
    ForeignKey,
    Index,
    CheckConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQL_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class TaskStatus(PyEnum):
    """任务状态枚举

    Linus原则：简单状态机，消除特殊情况
    - 只有4个状态，每个状态语义清晰
    - 状态转换：pending → processing → completed/failed
    - 没有"处理中但暂停"等复杂中间态
    """

    PENDING = "pending"  # 已创建，等待处理
    PROCESSING = "processing"  # 正在分析中
    COMPLETED = "completed"  # 分析完成
    FAILED = "failed"  # 分析失败


@dataclass
class TaskUpdate:
    """SSE任务状态更新数据结构

    Linus原则：统一数据结构，消除所有特殊情况
    - 单一TaskUpdate处理所有状态变化，无需connected/progress/error等特殊事件类型
    - progress永远存在（0-100），避免空值判断
    - message统一格式，提供用户友好的状态描述
    - 简洁的JSON序列化，直接用于SSE推送
    """

    task_id: str
    status: TaskStatus
    progress: int  # 0-100，永远存在
    message: str  # 统一消息格式："正在分析Reddit数据..."
    timestamp: datetime

    def to_json(self) -> str:
        """转换为SSE推送的JSON格式"""
        return json.dumps(
            {
                "task_id": self.task_id,
                "status": self.status.value,
                "progress": self.progress,
                "message": self.message,
                "timestamp": self.timestamp.isoformat(),
            },
            ensure_ascii=False,
        )

    def to_sse_format(self) -> str:
        """转换为SSE事件格式"""
        return f"data: {self.to_json()}\n\n"

    @classmethod
    def create_started(cls, task_id: str, message: str = "任务已开始") -> "TaskUpdate":
        """创建任务开始更新"""
        return cls(
            task_id=task_id,
            status=TaskStatus.PROCESSING,
            progress=0,
            message=message,
            timestamp=datetime.now(),
        )

    @classmethod
    def create_progress(cls, task_id: str, progress: int, message: str) -> "TaskUpdate":
        """创建进度更新"""
        return cls(
            task_id=task_id,
            status=TaskStatus.PROCESSING,
            progress=progress,
            message=message,
            timestamp=datetime.now(),
        )

    @classmethod
    def create_completed(cls, task_id: str, message: str = "分析完成") -> "TaskUpdate":
        """创建完成更新"""
        return cls(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            message=message,
            timestamp=datetime.now(),
        )

    @classmethod
    def create_failed(cls, task_id: str, message: str) -> "TaskUpdate":
        """创建失败更新"""
        return cls(
            task_id=task_id,
            status=TaskStatus.FAILED,
            progress=0,  # 失败时重置进度
            message=f"任务失败: {message}",
            timestamp=datetime.now(),
        )


class Task(Base):
    """用户分析任务模型

    Linus原则应用：
    1. 数据结构决定一切 - 状态字段驱动整个生命周期
    2. 消除特殊情况 - 所有字段都有明确的存在理由
    3. 约束下沉 - 业务逻辑在数据库层保证，不依赖应用验证
    4. 多租户原生 - 通过user_id天然支持数据隔离
    """

    __tablename__ = "tasks"

    # 主键：UUID类型，数据库生成
    id: UUID = Column(
        PostgreSQL_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        comment="任务唯一标识符",
    )

    # 外键关联：多租户通过用户实现数据隔离
    user_id: UUID = Column(
        PostgreSQL_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="任务所属用户ID，实现多租户数据隔离",
    )

    # 业务数据：分析目标描述
    product_description: str = Column(
        TEXT, nullable=False, comment="待分析的产品或服务描述，10-2000字符"
    )

    # 状态管理：简单4状态机
    # 注意：这里使用数据库的task_status枚举类型，不是Python枚举
    status: str = Column(
        String,  # PostgreSQL的ENUM在SQLAlchemy中映射为String
        nullable=False,
        server_default=text("'pending'::task_status"),
        comment="任务状态：pending/processing/completed/failed",
    )

    # 错误信息：失败时的详细信息
    error_message: Optional[str] = Column(
        TEXT, nullable=True, comment="任务失败时的错误描述"
    )

    # 审计字段：自动维护的时间戳
    created_at: datetime = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        comment="任务创建时间",
    )

    updated_at: datetime = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        comment="任务最后更新时间",
    )

    # 完成时间：仅在completed状态时有值
    completed_at: Optional[datetime] = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="任务完成时间（仅completed状态）",
    )

    # 关系映射：反向关联到用户
    user = relationship("User", back_populates="tasks")

    # 数据库约束和索引：确保数据完整性和查询性能
    __table_args__ = (
        # 业务约束：产品描述长度限制
        CheckConstraint(
            "char_length(product_description) BETWEEN 10 AND 2000",
            name="ck_tasks_description_length",
        ),
        # 状态一致性约束：错误信息只在failed状态存在
        CheckConstraint(
            "(status = 'failed' AND error_message IS NOT NULL) OR "
            "(status != 'failed' AND (error_message IS NULL OR error_message = ''))",
            name="ck_tasks_error_message_when_failed",
        ),
        # 完成时间一致性约束：只有completed状态才有completed_at
        CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status != 'completed' AND completed_at IS NULL)",
            name="ck_tasks_completed_at_consistency",
        ),
        # 时间逻辑约束：完成时间不能早于创建时间
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at",
            name="ck_tasks_time_logic",
        ),
        # 高频查询索引：用户任务状态查询
        Index("ix_tasks_user_status", "user_id", "status"),
        # 用户历史查询索引：按时间倒序
        Index("ix_tasks_user_created", "user_id", text("created_at DESC")),
        # 系统监控索引：按状态和时间查询
        Index("ix_tasks_status_created", "status", text("created_at DESC")),
        # 性能优化：处理中任务部分索引
        Index(
            "ix_tasks_processing",
            "status",
            "created_at",
            postgresql_where=text("status = 'processing'"),
        ),
        # 表注释
        {"comment": "用户分析任务表 - 跟踪Reddit信号分析请求的完整生命周期"},
    )

    # 业务方法：基于状态的操作

    def start_processing(self, notify_sse: bool = True) -> None:
        """开始处理任务

        状态转换：pending → processing
        只有pending状态的任务才能开始处理

        Args:
            notify_sse: 是否推送SSE更新，默认True
        """
        if self.status != TaskStatus.PENDING.value:
            raise ValueError(
                f"只有pending状态的任务才能开始处理，当前状态：{self.status}"
            )

        self.status = TaskStatus.PROCESSING.value
        # updated_at会被数据库触发器自动更新

        # 可选的SSE推送
        if notify_sse:
            self._notify_sse_update(TaskStatus.PROCESSING, 0, "任务开始处理")

    def mark_completed(
        self, completion_time: Optional[datetime] = None, notify_sse: bool = True
    ) -> None:
        """标记任务完成

        状态转换：processing → completed
        自动设置completed_at时间戳

        Args:
            completion_time: 完成时间，默认为当前时间
            notify_sse: 是否推送SSE更新，默认True
        """
        if self.status != TaskStatus.PROCESSING.value:
            raise ValueError(
                f"只有processing状态的任务才能标记完成，当前状态：{self.status}"
            )

        self.status = TaskStatus.COMPLETED.value
        self.completed_at = completion_time or func.current_timestamp()
        self.error_message = None  # 清除可能存在的错误信息

        # 可选的SSE推送
        if notify_sse:
            self._notify_sse_update(TaskStatus.COMPLETED, 100, "分析完成")

    def mark_failed(self, error_message: str, notify_sse: bool = True) -> None:
        """标记任务失败

        状态转换：processing → failed
        设置错误信息，清除完成时间

        Args:
            error_message: 错误描述信息
            notify_sse: 是否推送SSE更新，默认True
        """
        if self.status != TaskStatus.PROCESSING.value:
            raise ValueError(
                f"只有processing状态的任务才能标记失败，当前状态：{self.status}"
            )

        if not error_message or not error_message.strip():
            raise ValueError("失败任务必须提供错误信息")

        self.status = TaskStatus.FAILED.value
        self.error_message = error_message.strip()
        self.completed_at = None  # 清除可能存在的完成时间

        # 可选的SSE推送
        if notify_sse:
            self._notify_sse_update(
                TaskStatus.FAILED, 0, f"任务失败: {error_message.strip()}"
            )

    def reset_to_pending(self) -> None:
        """重置任务为待处理状态

        状态转换：failed → pending
        清除错误信息和完成时间，允许重试
        """
        if self.status != TaskStatus.FAILED.value:
            raise ValueError(f"只有failed状态的任务才能重置，当前状态：{self.status}")

        self.status = TaskStatus.PENDING.value
        self.error_message = None
        self.completed_at = None

    # SSE推送辅助方法

    def _notify_sse_update(
        self, status: TaskStatus, progress: int, message: str
    ) -> None:
        """推送SSE任务状态更新 - 基于Linus重构的广播器

        Linus原则：简化后的单一职责推送，使用全局广播替代队列映射

        Args:
            status: 任务状态
            progress: 进度百分比 (0-100)
            message: 用户友好的状态描述
        """
        try:
            # 使用重构后的简化广播器
            from ..services.simple_sse_broadcaster import get_sse_broadcaster

            broadcaster = get_sse_broadcaster()

            # 转换为异步调用，使用asyncio.create_task避免阻塞
            import asyncio

            asyncio.create_task(
                broadcaster.broadcast_task_update(
                    task_id=str(self.id),
                    status=status.value,
                    progress=progress,
                    message=message,
                )
            )
        except Exception as e:
            # SSE推送失败不应该影响任务状态更新
            # 只记录日志，不抛出异常
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"SSE广播失败 for task {self.id}: {e}")

    def notify_progress(self, progress: int, message: str) -> None:
        """推送进度更新 - 公共方法

        用于任务执行过程中推送进度更新，不改变数据库状态

        Args:
            progress: 进度百分比 (0-100)
            message: 进度描述
        """
        if not self.is_processing:
            # 只有processing状态才能推送进度
            return

        self._notify_sse_update(TaskStatus.PROCESSING, progress, message)

    # 查询便捷方法

    @property
    def is_pending(self) -> bool:
        """是否为待处理状态"""
        return self.status == TaskStatus.PENDING.value

    @property
    def is_processing(self) -> bool:
        """是否为处理中状态"""
        return self.status == TaskStatus.PROCESSING.value

    @property
    def is_completed(self) -> bool:
        """是否为已完成状态"""
        return self.status == TaskStatus.COMPLETED.value

    @property
    def is_failed(self) -> bool:
        """是否为失败状态"""
        return self.status == TaskStatus.FAILED.value

    @property
    def is_finished(self) -> bool:
        """是否为终态（已完成或失败）"""
        return self.status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value)

    def __repr__(self) -> str:
        """调试友好的字符串表示"""
        return (
            f"<Task(id={self.id}, user_id={self.user_id}, "
            f"status={self.status}, created={self.created_at.isoformat()[:19]})>"
        )

    def __str__(self) -> str:
        """用户友好的字符串表示"""
        desc_preview = (
            self.product_description[:50] + "..."
            if len(self.product_description) > 50
            else self.product_description
        )
        return f"任务{self.id}: {desc_preview} ({self.status})"


# Linus式设计说明：
#
# 1. 数据结构决定一切
#    - Task对象完全由status字段驱动行为
#    - 每个状态都有明确的数据要求和约束
#    - 状态转换通过方法强制，避免无效状态
#
# 2. 消除特殊情况
#    - 不存在"半完成"、"暂停"等模糊状态
#    - error_message和completed_at总是存在，但根据状态有不同含义
#    - 所有状态转换都有明确的前置条件检查
#
# 3. 约束下沉到数据库
#    - 长度限制、时间逻辑、状态一致性都在数据库层保证
#    - 应用层只需要处理业务逻辑，不需要验证数据格式
#    - 并发安全：数据库约束防止竞态条件
#
# 4. 索引基于查询模式
#    - ix_tasks_user_status: 用户看任务列表（最高频）
#    - ix_tasks_user_created: 用户看历史任务
#    - ix_tasks_processing: worker获取待处理任务
#    - 所有索引都支持多租户模式
#
# 5. 方法设计遵循单一职责
#    - 每个状态转换方法只做一件事
#    - 清晰的前置条件检查
#    - 自动维护相关字段一致性
#
# 6. 多租户原生支持
#    - user_id外键天然实现数据隔离
#    - 级联删除支持GDPR合规
#    - 所有查询都基于用户，性能有保证
