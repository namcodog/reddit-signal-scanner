"""
Reddit Signal Scanner - ORM基础类

基于 Linus 设计哲学：
- 继承自core.database.Base
- 提供通用字段和方法
- 保持简单，避免过度抽象
"""

# 重新导出Base类，保持一致性
from ..core.database import Base

__all__ = ["Base"]
