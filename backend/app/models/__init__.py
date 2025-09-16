"""
Reddit Signal Scanner - 数据模型模块

基于 Linus 设计原则：
- 简单的ORM映射，避免过度抽象
- 类型安全的Pydantic集成
- 清晰的数据关系定义

导出所有模型类供Alembic自动检测
"""

from .analysis import Analysis
from .base import Base
from .community_cache import CommunityCache
from .report import Report
from .task import Task
from .user import User

# 导出所有模型，供Alembic检测
__all__ = [
    "Base",
    "User",
    "Task",
    "Analysis",
    "Report",
    "CommunityCache",
]
