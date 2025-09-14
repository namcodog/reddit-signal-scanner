"""
Reddit Signal Scanner - 配置管理

Linus原则: "数据结构决定一切"
- 配置对象只负责数据，不验证
- 模块导入必须安全
- 验证逻辑独立，按需调用
- 消除所有特殊情况
"""

import os
from functools import lru_cache
from typing import Annotated, Any, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置 - 纯数据存储，无验证逻辑"""

    # 应用基础配置
    app_name: str = "Reddit Signal Scanner"
    app_version: str = "0.1.0"
    debug: Annotated[bool, Field(env="DEBUG")] = False  # 默认关闭DEBUG，需通过环境变量开启
    environment: Annotated[str, Field(env="ENVIRONMENT")] = "development"

    # 数据库配置
    database_url: Annotated[
        str, Field(env="DATABASE_URL")
    ] = "postgresql+asyncpg://postgres:postgres@localhost:5432/reddit_signal_scanner"
    database_pool_size: Annotated[int, Field(env="DB_POOL_SIZE")] = 10
    database_max_overflow: Annotated[int, Field(env="DB_MAX_OVERFLOW")] = 20
    database_pool_timeout: Annotated[int, Field(env="DB_POOL_TIMEOUT")] = 30

    # Redis配置
    redis_url: Annotated[str, Field(env="REDIS_URL")] = "redis://localhost:6379/0"

    # Mock开关（开发阶段默认启用）
    use_mocks: Annotated[bool, Field(env="USE_MOCKS")] = True

    # API版本与前缀
    api_version: Annotated[str, Field(env="API_VERSION")] = "v1"
    api_base: Annotated[str, Field(env="API_BASE")] = "/api"

    # Celery配置
    celery_broker_url: Annotated[
        str, Field(env="CELERY_BROKER_URL")
    ] = "redis://localhost:6379/1"
    celery_result_backend: Annotated[
        str, Field(env="CELERY_RESULT_BACKEND")
    ] = "redis://localhost:6379/2"

    # Reddit API配置
    reddit_client_id: Annotated[Optional[str], Field(env="REDDIT_CLIENT_ID")] = None
    reddit_client_secret: Annotated[
        Optional[str], Field(env="REDDIT_CLIENT_SECRET")
    ] = None
    reddit_user_agent: Annotated[
        str, Field(env="REDDIT_USER_AGENT")
    ] = "RedditSignalScanner/0.1.0"
    reddit_rate_limit: Annotated[int, Field(env="REDDIT_RATE_LIMIT")] = 60

    # JWT配置 - 支持RS256/HS256双算法架构
    jwt_secret_key: Annotated[
        str, Field(env="JWT_SECRET_KEY")
    ] = "dev-secret-key-change-in-production"
    jwt_algorithm: Annotated[str, Field(env="JWT_ALGORITHM")] = "HS256"
    jwt_algorithms: Annotated[
        str, Field(env="JWT_ALGORITHMS")
    ] = "RS256,HS256"  # 支持的算法列表
    jwt_access_token_expire_minutes: Annotated[
        int, Field(env="JWT_EXPIRE_MINUTES")
    ] = 1440  # 24小时
    jwt_refresh_token_expire_days: Annotated[
        int, Field(env="JWT_REFRESH_EXPIRE_DAYS")
    ] = 7

    # RS256密钥配置
    jwt_private_key_path: Annotated[
        Optional[str], Field(env="JWT_PRIVATE_KEY_PATH")
    ] = None
    jwt_public_key_path: Annotated[
        Optional[str], Field(env="JWT_PUBLIC_KEY_PATH")
    ] = None
    jwt_key_id: Annotated[Optional[str], Field(env="JWT_KEY_ID")] = "rss-key-1"

    # 密钥轮换配置
    jwt_key_rotation_enabled: Annotated[
        bool, Field(env="JWT_KEY_ROTATION_ENABLED")
    ] = False
    jwt_key_rotation_days: Annotated[int, Field(env="JWT_KEY_ROTATION_DAYS")] = 90

    # 文件上传配置
    upload_max_size: Annotated[int, Field(env="UPLOAD_MAX_SIZE")] = 10485760  # 10MB
    upload_allowed_types: Annotated[
        str, Field(env="UPLOAD_ALLOWED_TYPES")
    ] = "text/plain,application/json"

    # 性能配置
    max_concurrent_tasks: Annotated[int, Field(env="MAX_CONCURRENT_TASKS")] = 5
    analysis_timeout_seconds: Annotated[int, Field(env="ANALYSIS_TIMEOUT")] = 300
    cache_ttl_seconds: Annotated[int, Field(env="CACHE_TTL")] = 3600

    # 清理配置
    cleanup_interval_hours: Annotated[int, Field(env="CLEANUP_INTERVAL")] = 24
    keep_completed_tasks_days: Annotated[int, Field(env="KEEP_COMPLETED_DAYS")] = 30
    keep_failed_tasks_days: Annotated[int, Field(env="KEEP_FAILED_DAYS")] = 7

    # 日志配置
    log_level: Annotated[str, Field(env="LOG_LEVEL")] = "INFO"
    log_format: Annotated[
        str, Field(env="LOG_FORMAT")
    ] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    @property
    def database_url_sync(self) -> str:
        """同步数据库连接字符串（Alembic专用）"""
        return self.database_url.replace("+asyncpg", "")

    @property
    def upload_allowed_types_list(self) -> list[str]:
        """文件类型列表"""
        return [t.strip() for t in self.upload_allowed_types.split(",")]

    @property
    def jwt_algorithms_list(self) -> list[str]:
        """JWT支持算法列表"""
        return [alg.strip() for alg in self.jwt_algorithms.split(",")]

    @property
    def jwt_access_token_expire_seconds(self) -> int:
        """JWT访问令牌过期时间（秒）"""
        return self.jwt_access_token_expire_minutes * 60

    @property
    def jwt_refresh_token_expire_seconds(self) -> int:
        """JWT刷新令牌过期时间（秒）"""
        return self.jwt_refresh_token_expire_days * 24 * 3600

    @property
    def api_prefix(self) -> str:
        """统一的API前缀，如 /api/v1"""
        return f"{self.api_base.rstrip('/')}/{self.api_version.lstrip('/')}"

    @property
    def API_PREFIX(self) -> str:
        """兼容性别名，等同于 api_prefix"""
        return self.api_prefix

    @property
    def is_production(self) -> bool:
        """生产环境判断"""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """开发环境判断"""
        return self.environment.lower() == "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# ===== 验证逻辑分离 =====


def validate_production_config(settings: Settings) -> list[str]:
    """生产环境配置验证 - 独立函数，按需调用"""
    issues = []

    # JWT密钥检查
    if (
        settings.is_production
        and settings.jwt_secret_key == "dev-secret-key-change-in-production"
    ):
        issues.append("生产环境必须设置自定义JWT_SECRET_KEY")

    # 数据库URL检查
    if not settings.database_url.startswith(("postgresql://", "postgresql+asyncpg://")):
        issues.append("database_url必须是PostgreSQL连接字符串")

    # Redis URL检查
    redis_urls = [
        settings.redis_url,
        settings.celery_broker_url,
        settings.celery_result_backend,
    ]
    for url in redis_urls:
        if not url.startswith("redis://"):
            issues.append(f"Redis URL格式错误: {url}")

    return issues


def validate_config_connectivity(settings: Settings) -> list[str]:
    """连接性验证 - 可选的深度验证"""
    issues: list[str] = []

    # 这里可以添加实际的连接测试
    # 比如：尝试连接数据库、Redis等
    # 但只在明确需要时调用，不在模块导入时执行

    return issues


# ===== 安全的配置获取 =====


@lru_cache()
def get_settings() -> Settings:
    """获取配置对象 - 保证导入安全"""
    return Settings()


def get_validated_settings() -> Settings:
    """获取经过验证的配置 - 主动验证模式"""
    settings = get_settings()

    # 只在生产环境或明确要求时验证
    if settings.is_production:
        issues = validate_production_config(settings)
        if issues:
            raise ValueError(f"生产环境配置错误: {'; '.join(issues)}")

    return settings


def check_config_health() -> dict[str, Any]:
    """配置健康检查 - 诊断工具"""
    settings = get_settings()

    return {
        "environment": settings.environment,
        "debug_mode": settings.debug,
        "production_issues": validate_production_config(settings),
        "connectivity_issues": validate_config_connectivity(settings),
        "config_source": ("environment" if os.getenv("DATABASE_URL") else "defaults"),
    }
