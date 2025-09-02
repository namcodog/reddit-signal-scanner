"""
报告缓存数据模型 - Linus式简单设计

原则：数据库存储数据，应用处理逻辑
- SQLAlchemy ORM模型：纯数据映射
- Pydantic Schema：基本API验证
- 一对多关系：支持报告版本管理
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel, Field

from .base import Base


# ===== SQLAlchemy ORM 模型 =====


class Report(Base):
    """报告缓存ORM模型 - 纯数据映射"""

    __tablename__ = "reports"

    # 基本字段
    id = Column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    analysis_id = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
    )
    html_content = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # 关系映射
    analysis = relationship("Analysis", back_populates="reports")

    # 表级约束
    __table_args__ = (
        CheckConstraint(
            "length(html_content) <= 10485760", name="ck_reports_html_size"
        ),
        CheckConstraint(
            "status IN ('active', 'deprecated', 'draft')", name="ck_reports_status"
        ),
    )

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, analysis_id={self.analysis_id}, status={self.status})>"


# ===== Pydantic Schema 模型 =====


class ReportCreateRequest(BaseModel):
    """创建报告请求"""

    analysis_id: UUID
    html_content: str = Field(..., min_length=1, max_length=10485760)
    status: str = Field(default="active", pattern=r"^(active|deprecated|draft)$")


class ReportResponse(BaseModel):
    """报告响应"""

    id: UUID
    analysis_id: UUID
    html_content: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ===== 工具函数 =====


def create_report(
    analysis_id: UUID, html_content: str, status: str = "active"
) -> Report:
    """创建报告记录"""
    return Report(analysis_id=analysis_id, html_content=html_content, status=status)
