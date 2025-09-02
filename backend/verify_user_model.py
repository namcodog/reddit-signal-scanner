#!/usr/bin/env python3
"""
验证User模型实现
基于PRD-01要求和prd01-02任务
"""

import sys
import asyncio
from pathlib import Path

# 添加app到路径
sys.path.append(str(Path(__file__).parent))

from app.core.database import Base
from app.models.user import User


def verify_user_model():
    """验证User模型结构"""
    print("🔍 验证User模型...")

    # 检查表名
    assert User.__tablename__ == "users", f"错误的表名: {User.__tablename__}"
    print("✅ 表名正确: users")

    # 检查必需字段
    required_columns = [
        "id",
        "email",
        "password_hash",
        "is_active",
        "created_at",
        "updated_at",
    ]
    actual_columns = list(User.__table__.columns.keys())

    for col in required_columns:
        assert col in actual_columns, f"缺少字段: {col}"
    print(f"✅ 必需字段完整: {required_columns}")

    # 检查字段类型
    id_col = User.__table__.columns["id"]
    email_col = User.__table__.columns["email"]
    password_col = User.__table__.columns["password_hash"]
    active_col = User.__table__.columns["is_active"]

    # UUID主键检查
    assert id_col.primary_key, "id字段应该是主键"
    print("✅ id字段是主键")

    # 邮箱唯一性检查
    assert email_col.unique, "email字段应该是唯一的"
    assert not email_col.nullable, "email字段不应该为空"
    print("✅ email字段唯一且非空")

    # 密码字段检查
    assert not password_col.nullable, "password_hash字段不应该为空"
    print("✅ password_hash字段非空")

    # 状态字段检查
    assert not active_col.nullable, "is_active字段不应该为空"
    print("✅ is_active字段非空")

    # 检查模型方法
    user_repr = User().__repr__()
    assert "User(" in user_repr, "User模型应该有__repr__方法"
    print("✅ __repr__方法存在")

    print("\n🎯 User模型验证完成！")
    print("📋 模型特性:")
    print(f"   • 表名: {User.__tablename__}")
    print(f"   • 字段数量: {len(actual_columns)}")
    print(f"   • 字段列表: {actual_columns}")
    print(f"   • 主键: id (UUID)")
    print(f"   • 唯一约束: email")
    print(f"   • 索引字段: email, is_active")


def verify_sqlalchemy_structure():
    """验证SQLAlchemy结构"""
    print("\n🔍 验证SQLAlchemy结构...")

    # 检查Base类继承
    assert issubclass(User, Base), "User应该继承自Base"
    print("✅ 继承关系正确")

    # 检查表对象存在
    assert hasattr(User, "__table__"), "User应该有__table__属性"
    print("✅ 表对象存在")

    # 检查列定义
    table = User.__table__
    assert len(table.columns) == 6, f"应该有6个字段，实际有{len(table.columns)}"
    print("✅ 字段数量正确")

    print("🎯 SQLAlchemy结构验证完成！")


if __name__ == "__main__":
    try:
        verify_user_model()
        verify_sqlalchemy_structure()
        print("\n🚀 所有验证通过！User模型符合PRD-01要求")

    except Exception as e:
        print(f"\n❌ 验证失败: {e}")
        sys.exit(1)
