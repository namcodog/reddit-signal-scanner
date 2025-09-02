#!/usr/bin/env python3
"""
Reddit Signal Scanner - 数据库验证脚本

用于验证：
1. 配置加载正确性
2. 数据库连接能力
3. Alembic迁移配置
4. 基础表结构检查

运行方式：
cd backend && python verify_db.py
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from app.core.config import get_settings, check_config_health
    from app.core.database import check_database_health, get_engine
    from sqlalchemy import text
    import logging

    # 配置日志
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请确保在backend目录下运行此脚本")
    sys.exit(1)


async def verify_config():
    """验证配置加载"""
    print("🔧 验证应用配置...")
    try:
        settings = get_settings()
        print(f"✅ 应用名称: {settings.app_name}")
        print(f"✅ 数据库URL: {settings.database_url}")
        print(f"✅ 调试模式: {settings.debug}")
        return True
    except Exception as e:
        print(f"❌ 配置验证失败: {e}")
        return False


async def verify_database_connection():
    """验证数据库连接"""
    print("\n🔌 验证数据库连接...")
    try:
        # 使用健康检查函数
        health_result = await check_database_health()
        if health_result["status"] == "healthy":
            print("✅ 数据库连接正常")
            print(f"✅ 连接状态: {health_result['connection']}")
            return True
        else:
            print(f"❌ 数据库健康检查失败: {health_result.get('error', '未知错误')}")
            return False
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("请确保PostgreSQL服务正在运行，并且连接信息正确")
        return False


async def verify_basic_queries():
    """验证基础SQL查询"""
    print("\n📊 验证基础SQL查询...")
    try:
        from app.core.database import get_session_factory

        session_factory = get_session_factory()
        async with session_factory() as session:
            # 测试基础查询
            result = await session.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ PostgreSQL版本: {version}")

            # 检查扩展
            result = await session.execute(
                text(
                    "SELECT extname FROM pg_extension WHERE extname IN ('uuid-ossp', 'btree_gin')"
                )
            )
            extensions = [row[0] for row in result.fetchall()]
            print(f"✅ 已安装扩展: {extensions}")

        return True
    except Exception as e:
        print(f"❌ SQL查询验证失败: {e}")
        return False


def verify_alembic_config():
    """验证Alembic配置"""
    print("\n⚙️ 验证Alembic配置...")
    try:
        # 检查Alembic配置文件
        alembic_ini = project_root / "alembic.ini"
        if not alembic_ini.exists():
            print("❌ alembic.ini 文件不存在")
            return False

        print("✅ alembic.ini 文件存在")

        # 检查迁移目录
        alembic_dir = project_root / "alembic"
        if not alembic_dir.exists():
            print("❌ alembic 目录不存在")
            return False

        print("✅ alembic 目录存在")

        # 检查env.py
        env_py = alembic_dir / "env.py"
        if not env_py.exists():
            print("❌ alembic/env.py 文件不存在")
            return False

        print("✅ alembic/env.py 文件存在")

        # 检查迁移文件
        versions_dir = alembic_dir / "versions"
        migration_files = list(versions_dir.glob("*.py"))
        print(f"✅ 发现 {len(migration_files)} 个迁移文件")

        for migration in migration_files:
            print(f"  - {migration.name}")

        return True
    except Exception as e:
        print(f"❌ Alembic配置验证失败: {e}")
        return False


def print_next_steps():
    """输出后续步骤指导"""
    print("\n🚀 后续步骤:")
    print("1. 如果使用Docker，启动数据库：docker-compose up -d postgres")
    print("2. 创建数据库：createdb reddit_scanner")
    print("3. 运行初始迁移：alembic upgrade head")
    print("4. 验证表结构：psql reddit_scanner -c '\\dt'")


async def main():
    """主验证流程"""
    print("🔍 Reddit Signal Scanner - 数据库基础设施验证")
    print("=" * 60)

    results = []

    # 配置验证
    results.append(await verify_config())

    # 数据库连接验证
    results.append(await verify_database_connection())

    # 基础查询验证（仅在连接成功时）
    if results[-1]:
        results.append(await verify_basic_queries())

    # Alembic配置验证
    results.append(verify_alembic_config())

    # 结果汇总
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"🎉 所有验证通过！({passed}/{total})")
        print("✅ 数据库基础设施配置完成")
    else:
        print(f"⚠️ 部分验证失败 ({passed}/{total})")
        print_next_steps()

    # 清理连接
    try:
        engine = get_engine()
        await engine.dispose()
    except:
        pass


if __name__ == "__main__":
    asyncio.run(main())
