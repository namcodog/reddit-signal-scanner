#!/usr/bin/env python3
"""
简单的数据库连接测试

验证数据库是否可以连接，为PRD01-10测试做准备。
"""

import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def test_database_connection():
    """测试数据库连接"""
    # 使用简单的测试数据库URL
    database_url = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"

    try:
        print("🔌 尝试连接数据库...")
        engine = create_async_engine(database_url, echo=True)

        async with engine.begin() as conn:
            # 测试基本查询
            result = await conn.execute(text("SELECT 1 as test"))
            test_value = result.scalar()

            print(f"✅ 数据库连接成功! 测试查询返回: {test_value}")

            # 检查是否可以创建测试数据库
            try:
                await conn.execute(text("CREATE DATABASE reddit_scanner_test"))
                print("✅ 测试数据库创建成功")
            except Exception as e:
                if "already exists" in str(e):
                    print("ℹ️ 测试数据库已存在")
                else:
                    print(f"⚠️ 创建测试数据库时出现问题: {e}")

        await engine.dispose()
        return True

    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("💡 请确保:")
        print("   1. PostgreSQL服务正在运行")
        print("   2. 用户名密码正确")
        print("   3. 数据库服务器可访问")
        return False


async def main():
    """主函数"""
    print("🚀 PRD01-10 数据库连接验证")
    print("=" * 40)

    success = await test_database_connection()

    if success:
        print("\n🎉 数据库连接验证通过!")
        print("📋 可以继续执行PRD01-10验证测试")
        sys.exit(0)
    else:
        print("\n❌ 数据库连接验证失败!")
        print("🔧 请先修复数据库连接问题")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
