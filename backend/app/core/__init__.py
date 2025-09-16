"""
Reddit Signal Scanner - 核心配置模块

Linus设计哲学：
- 简单配置，延迟初始化
- 环境变量优先，容器友好
- 模块导入安全，无副作用

导出核心组件：
- Settings: 应用配置
- get_db: 数据库会话管理器
- get_engine: 数据库引擎工厂
- Base: ORM基类
"""

from .config import Settings, check_config_health, get_settings
from .database import Base, get_db, get_engine, get_session_factory

__all__ = [
    "Settings",
    "get_settings",
    "check_config_health",
    "get_db",
    "get_engine",
    "get_session_factory",
    "Base",
]
