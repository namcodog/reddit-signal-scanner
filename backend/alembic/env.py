"""
Reddit Signal Scanner - Alembic 环境配置

基于 Linus 设计原则：
- 简单的迁移逻辑，避免复杂抽象
- 支持异步数据库操作
- 自动检测模型变更

功能：
- 从环境变量读取数据库连接
- 自动导入所有模型进行对比
- 支持离线和在线迁移模式
"""

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 添加 app 目录到 Python 路径
sys.path.append(str(Path(__file__).resolve().parents[1]))

# 导入应用配置和模型
from app.core.config import get_settings
from app.core.database import Base

# 获取应用配置
settings = get_settings()

# Alembic Config 对象
config = context.config

# 设置数据库连接URL（从环境变量）
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

# 解释配置文件中的日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 目标元数据（包含所有模型定义）
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """运行离线迁移模式

    此模式下不需要实际连接数据库
    仅生成 SQL 脚本
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # 重要：设置模式前缀
        version_table_schema=target_metadata.schema,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """执行迁移的核心逻辑"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # 重要：设置模式前缀
        version_table_schema=target_metadata.schema,
        # 比较类型变更
        compare_type=True,
        # 比较服务器默认值
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """运行异步迁移

    使用异步引擎连接数据库
    支持 asyncpg 驱动
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """运行在线迁移模式

    创建实际数据库连接并执行迁移
    """
    asyncio.run(run_async_migrations())


# 判断运行模式并执行相应的迁移逻辑
if context.is_offline_mode():
    print("🔄 运行离线迁移模式...")
    run_migrations_offline()
else:
    print("🔄 运行在线迁移模式...")
    run_migrations_online()
    print("✅ 迁移完成")
