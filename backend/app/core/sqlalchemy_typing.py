"""
SQLAlchemy 类型辅助 - 统一布尔子句与泛型约束

用途：
- 为 SQLAlchemy 过滤条件提供显式的 ColumnElement[bool] 类型包装
- 避免 mypy [bool] 误判
"""

from typing import Any, TypeVar, cast

from sqlalchemy.sql.elements import ColumnElement

BoolClause = ColumnElement[bool]
T = TypeVar("T")


def as_bool_clause(expr: Any) -> BoolClause:
    """将任意 SQLAlchemy 表达式转换为布尔子句类型。

    注意：该函数仅用于类型提示收敛，不改变运行时行为。
    """
    return cast(BoolClause, expr)
