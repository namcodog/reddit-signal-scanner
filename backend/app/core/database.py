"""
Reddit Signal Scanner - 数据库连接管理

Linus原则: "简单可靠，延迟初始化"
- 模块导入必须安全，不创建任何连接
- 数据库对象按需创建，延迟初始化
- 异步引擎使用默认连接池，不指定poolclass
- 事件监听器只在需要时注册
"""

import logging
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, TypedDict, Union, cast

import yaml
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from typing_extensions import NotRequired

from .config import get_settings
from .types import JsonValue

# 全局变量，延迟初始化
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
_logger = logging.getLogger(__name__)
_db_config: Optional["DatabaseConfig"] = None


# =============================
# 类型安全的数据结构定义
# =============================


class ConnectionLimits(TypedDict, total=False):
    max_connections: int


class ConnectionsConfig(TypedDict, total=False):
    statement_timeout: Union[int, str]
    idle_in_transaction_session_timeout: Union[int, str]
    lock_timeout: Union[int, str]


class MemoryConfig(TypedDict, total=False):
    shared_buffers: str


class JsonbOptimizationConfig(TypedDict, total=False):
    enabled: NotRequired[bool]


class DatabaseConfig(TypedDict, total=False):
    connection_limits: ConnectionLimits
    connections: ConnectionsConfig
    memory: MemoryConfig
    jsonb_optimization: JsonbOptimizationConfig
    multi_tenant: bool


class ConnectArgs(TypedDict, total=False):
    options: str
    server_settings: Dict[str, str]


class ConnectionParams(TypedDict):
    pool_size: int
    max_overflow: int
    pool_timeout: int
    pool_pre_ping: bool
    pool_recycle: int
    pool_reset_on_return: str  # Context7优化：连接重置策略
    connect_args: ConnectArgs
    echo: bool
    echo_pool: bool
    future: bool


class Base(DeclarativeBase):
    """SQLAlchemy ORM 基类 - 纯数据结构，无副作用"""

    pass


def load_database_config() -> DatabaseConfig:
    """加载环境特定的数据库配置 - Linus原则：消除特殊情况"""
    global _db_config
    if _db_config is None:
        settings = get_settings()
        config_path = Path(__file__).parent.parent.parent / "config" / "database.yml"

        try:
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)

                # 获取环境特定配置，消除环境分支特殊情况
                env_config = config.get(settings.environment, {})
                common_config = config.get("common", {})

                # 合并通用配置和环境特定配置
                merged = {**common_config, **env_config}
                _db_config = cast(DatabaseConfig, merged)
                _logger.info(
                    "Database config loaded successfully - env: %s",
                    settings.environment,
                )
            else:
                _db_config = cast(DatabaseConfig, {})
                _logger.warning(f"⚠️ 数据库配置文件未找到: {config_path}")

        except Exception as e:
            _logger.error(f"❌ 数据库配置加载失败: {e}")
            _db_config = cast(DatabaseConfig, {})

    return _db_config


def get_connection_params() -> ConnectionParams:
    """获取数据库连接参数 - Context7最佳实践优化"""
    settings = get_settings()
    db_config = load_database_config()

    # 从配置文件获取连接限制，回退到默认值
    connection_limits: ConnectionLimits = db_config.get("connection_limits", {})

    # Context7推荐：优化连接池大小适应高并发
    base_pool_size = connection_limits.get(
        "max_connections", settings.database_pool_size
    )
    optimized_pool_size = max(10, base_pool_size // 3)  # 最小10，最大1/3

    return {
        # 连接池配置 - Context7性能优化
        "pool_size": optimized_pool_size,
        "max_overflow": min(30, settings.database_max_overflow * 2),  # 增加溢出
        "pool_timeout": 60,  # Context7推荐：增加获取连接超时
        "pool_pre_ping": True,  # Context7关键优化：连接健康检查
        "pool_recycle": 7200,  # Context7推荐：2小时回收连接
        # Context7优化：连接复用和清理
        "pool_reset_on_return": "commit",  # 返回时重置事务状态
        # 新增：基于配置的优化参数
        "connect_args": _get_connect_args(db_config),
        # 调试配置 - 生产环境关闭pool日志
        "echo": settings.debug,
        "echo_pool": False,  # Context7推荐：减少日志输出
        "future": True,
    }


def _get_connect_args(db_config: DatabaseConfig) -> ConnectArgs:
    """获取数据库连接参数 - 将配置转换为连接参数"""
    connect_args: ConnectArgs = {}
    settings = get_settings()
    url = getattr(settings, "database_url", "")

    # 从配置文件获取连接相关参数
    connections_config: ConnectionsConfig = db_config.get("connections", {})
    if connections_config:
        # 根据驱动选择参数：asyncpg 使用 server_settings；psycopg2 使用 options
        use_asyncpg = "+asyncpg" in url
        if use_asyncpg:
            server_settings: Dict[str, str] = {}
            if "statement_timeout" in connections_config:
                server_settings["statement_timeout"] = str(
                    connections_config["statement_timeout"]
                )
            if "idle_in_transaction_session_timeout" in connections_config:
                server_settings["idle_in_transaction_session_timeout"] = str(
                    connections_config["idle_in_transaction_session_timeout"]
                )
            if "lock_timeout" in connections_config:
                server_settings["lock_timeout"] = str(
                    connections_config["lock_timeout"]
                )
            if server_settings:
                connect_args["server_settings"] = server_settings
        else:
            if "statement_timeout" in connections_config:
                timeout_val = connections_config["statement_timeout"]
                connect_args["options"] = (
                    connect_args.get("options", "")
                    + f" -c statement_timeout={timeout_val}"
                )
            if "idle_in_transaction_session_timeout" in connections_config:
                idle_timeout = connections_config["idle_in_transaction_session_timeout"]
                connect_args["options"] = (
                    connect_args.get("options", "")
                    + f" -c idle_in_transaction_session_timeout={idle_timeout}"
                )
            if "lock_timeout" in connections_config:
                lock_timeout = connections_config["lock_timeout"]
                connect_args["options"] = (
                    connect_args.get("options", "") + f" -c lock_timeout={lock_timeout}"
                )

    return connect_args


def get_engine() -> AsyncEngine:
    """获取数据库引擎 - 延迟初始化，线程安全，基于配置优化"""
    global _engine
    if _engine is None:
        settings = get_settings()

        # 获取优化的连接参数
        conn_params = get_connection_params()

        # 创建异步引擎 - 使用配置优化参数
        _engine = create_async_engine(settings.database_url, **conn_params)

        # 只在debug模式注册事件监听器
        if settings.debug:
            _register_debug_events(_engine)

        _logger.info("Database engine initialized with Context7 optimization")

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取会话工厂 - 延迟初始化"""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False,
        )

        # 设置多租户数据隔离 - 基于context7最佳实践
        try:
            from .tenant_isolation import setup_tenant_isolation

            setup_tenant_isolation(_session_factory)
            _logger.info("✅ 多租户数据隔离已启用")
        except ImportError:
            _logger.warning("⚠️ 租户隔离模块未找到，跳过多租户设置")

        _logger.info("✅ 会话工厂初始化完成")

    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """数据库会话依赖注入 - FastAPI专用

    使用方式:
        async def endpoint(db: AsyncSession = Depends(get_db)):
            # 数据库操作
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            _logger.debug("数据库会话创建")
            yield session
            await session.commit()
            _logger.debug("数据库会话提交")
        except Exception as e:
            await session.rollback()
            _logger.error(f"数据库会话回滚: {e}")
            raise
        finally:
            await session.close()
            _logger.debug("数据库会话关闭")


def _register_debug_events(engine: AsyncEngine) -> None:
    """注册调试事件监听器 - 仅调试模式"""

    @event.listens_for(engine.sync_engine, "connect")
    def on_connect(dbapi_connection: Any, connection_record: Any) -> None:
        _logger.info(f"数据库连接建立: {id(dbapi_connection)}")

    @event.listens_for(engine.sync_engine, "checkout")
    def on_checkout(
        dbapi_connection: Any, connection_record: Any, connection_proxy: Any
    ) -> None:
        _logger.debug(f"连接检出: {id(dbapi_connection)}")

    @event.listens_for(engine.sync_engine, "checkin")
    def on_checkin(dbapi_connection: Any, connection_record: Any) -> None:
        _logger.debug(f"连接归还: {id(dbapi_connection)}")


async def init_database() -> None:
    """初始化数据库表 - 应用启动时调用"""
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            # 导入模型（如果存在）
            try:
                from ..models import CommunityCache  # noqa: F401

                _logger.info("✅ 数据模型导入成功")
            except ImportError as e:
                _logger.warning(f"⚠️ 数据模型导入警告: {e}")

            # 创建所有表
            await conn.run_sync(Base.metadata.create_all)
            _logger.info("✅ 数据库表创建成功")

    except Exception as e:
        _logger.error(f"❌ 数据库初始化失败: {e}")
        raise


async def close_database() -> None:
    """关闭数据库连接 - 应用关闭时调用"""
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        _logger.info("Database connections closed and disposed")


async def check_database_health() -> dict[str, JsonValue]:
    """数据库健康检查 - 诊断工具，包含配置状态"""
    try:
        engine = get_engine()
        db_config = load_database_config()
        settings = get_settings()

        async with engine.begin() as conn:
            from sqlalchemy import text

            result = await conn.execute(text("SELECT 1"))
            row = result.fetchone()

        return {
            "status": "healthy",
            "connection": "active" if _engine else "inactive",
            "test_query": "passed" if row and row[0] == 1 else "failed",
            "pool_status": (
                {
                    "size": getattr(engine.pool, "size", lambda: 0)(),
                    "checked_in": getattr(engine.pool, "checkedin", lambda: 0)(),
                    "checked_out": getattr(engine.pool, "checkedout", lambda: 0)(),
                }
                if hasattr(engine, "pool")
                else None
            ),
            "configuration": {
                "environment": settings.environment,
                "config_loaded": bool(db_config),
                "optimization_enabled": bool(
                    db_config.get("memory") or db_config.get("connections")
                ),
                "jsonb_optimization": bool(db_config.get("jsonb_optimization")),
                "multi_tenant": bool(db_config.get("multi_tenant")),
            },
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "connection": "failed",
            "configuration": {"config_error": str(e)},
        }


class ConfigSummary(TypedDict):
    environment: str
    memory_optimized: bool
    jsonb_optimized: bool
    multi_tenant_ready: bool


class ValidationResult(TypedDict):
    valid: bool
    issues: List[str]
    warnings: List[str]
    config_summary: ConfigSummary


def validate_database_config() -> ValidationResult:
    """验证数据库配置 - 独立的配置验证函数"""
    db_config = load_database_config()
    settings = get_settings()
    issues = []
    warnings: List[str] = []

    # 检查必要的配置节是否存在
    if not db_config:
        issues.append("数据库配置文件缺失或为空")
        return {
            "valid": False,
            "issues": issues,
            "warnings": warnings,
            "config_summary": {
                "environment": settings.environment,
                "memory_optimized": False,
                "jsonb_optimized": False,
                "multi_tenant_ready": False,
            },
        }

    # 检查内存配置
    memory_config: MemoryConfig = db_config.get("memory", {})
    if memory_config:
        shared_buffers = memory_config.get("shared_buffers", "0MB")
        if "512MB" not in shared_buffers and settings.environment == "production":
            warnings.append(f"生产环境shared_buffers配置为{shared_buffers}，建议512MB")
    else:
        warnings.append("未找到内存优化配置")

    # 检查连接配置
    connection_limits = db_config.get("connection_limits", {})
    if connection_limits:
        max_connections = connection_limits.get("max_connections", 0)
        if max_connections < 100 and settings.environment == "production":
            warnings.append(f"生产环境最大连接数为{max_connections}，建议至少100")
    else:
        warnings.append("未找到连接限制配置")

    # 检查JSONB优化配置
    jsonb_config: JsonbOptimizationConfig = db_config.get("jsonb_optimization", {})
    if not jsonb_config:
        warnings.append("未找到JSONB优化配置")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "config_summary": {
            "environment": settings.environment,
            "memory_optimized": bool(memory_config),
            "jsonb_optimized": bool(jsonb_config),
            "multi_tenant_ready": bool(db_config.get("multi_tenant")),
        },
    }


# 便捷函数 - 直接获取会话
async def get_session() -> AsyncSession:
    """直接获取数据库会话 - 手动管理模式"""
    session_factory = get_session_factory()
    async_session: AsyncSession = session_factory()
    return async_session


# ====================================================================
# 同步数据库访问 - Celery任务专用
# ====================================================================


# 同步引擎和会话工厂（延迟初始化）
_sync_engine = None
_sync_session_factory = None


def get_sync_engine() -> Engine:
    """获取同步数据库引擎 - Celery任务专用"""
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()

        # 将异步URL转换为同步URL
        sync_url = settings.database_url.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        )

        # 获取连接参数（去掉异步特定的）
        conn_params = get_connection_params()
        # 复制为普通dict以便移除异步特定参数
        conn_params_copy: Dict[str, object] = dict(conn_params)
        conn_params_copy.pop("future", None)
        conn_params_copy.pop("echo_pool", None)

        _sync_engine = create_engine(sync_url, **conn_params_copy)
        _logger.info("✅ 同步数据库引擎初始化完成（Celery专用）")

    return _sync_engine


def get_sync_session_factory() -> sessionmaker[Session]:
    """获取同步会话工厂"""
    global _sync_session_factory
    if _sync_session_factory is None:
        engine = get_sync_engine()
        _sync_session_factory = sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False,
        )
        _logger.info("✅ 同步会话工厂初始化完成")

    return _sync_session_factory


def get_session_sync() -> Session:
    """获取同步数据库会话 - Celery任务专用

    Returns:
        Session: 同步数据库会话
    """
    session_factory = get_sync_session_factory()
    return session_factory()
