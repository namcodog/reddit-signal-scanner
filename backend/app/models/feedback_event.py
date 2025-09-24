"""
统一反馈事件表 - feedback_events

用途：沉淀 Admin/前台 反馈与决策事件，支持后续聚合与审计。

字段设计（最小可用）：
- id: 主键 UUID（服务端生成）
- source: 事件来源（user|admin|system）
- event_type: 事件类型（community_decision|analysis_rating|insight_flag|metric）
- user_id: 产生该事件的用户（可空）
- task_id: 关联任务ID（文本，可空）
- analysis_id: 关联分析ID（文本，可空）
- payload: JSONB 原始数据（包含事件完整上下文）
- created_at: 创建时间（默认 now()）
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import TEXT, TIMESTAMP, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base
from ..core.types import JsonValue


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        comment="事件ID",
    )

    source: Mapped[str] = mapped_column(
        TEXT,
        nullable=False,
        comment="来源：user|admin|system",
    )

    event_type: Mapped[str] = mapped_column(
        TEXT,
        nullable=False,
        comment="类型：community_decision|analysis_rating|insight_flag|metric",
    )

    user_id: Mapped[Optional[str]] = mapped_column(
        TEXT, nullable=True, comment="用户ID（文本，兼容外部来源）"
    )
    task_id: Mapped[Optional[str]] = mapped_column(
        TEXT, nullable=True, comment="任务ID（文本，非强绑定）"
    )
    analysis_id: Mapped[Optional[str]] = mapped_column(
        TEXT, nullable=True, comment="分析ID（文本，非强绑定）"
    )

    payload: Mapped[dict[str, JsonValue]] = mapped_column(
        JSONB, nullable=False, comment="事件原始负载（JSONB）"
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        comment="创建时间",
    )

    __table_args__ = (
        CheckConstraint("source IN ('user','admin','system')", name="ck_feedback_source"),
        CheckConstraint(
            "event_type IN ('community_decision','analysis_rating','insight_flag','metric','moderation_action')",
            name="ck_feedback_event_type",
        ),
    )
