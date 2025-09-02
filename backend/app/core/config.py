"""
Reddit Signal Scanner - 配置管理

Linus原则: "数据结构决定一切"
- 配置对象只负责数据，不验证
- 模块导入必须安全
- 验证逻辑独立，按需调用
- 消除所有特殊情况
"""

from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    """应用配置 - 纯数据存储，无验证逻辑"""

    # 应用基础配置
    app_name: str = "Reddit Signal Scanner"
    app_version: str = "0.1.0"
    debug: bool = Field(default=True, env="DEBUG")  # 开发环境默认DEBUG=True
    environment: str = Field(default="development", env="ENVIRONMENT")

    # 数据库配置
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/reddit_scanner",
        env="DATABASE_URL",
    )
    database_pool_size: int = Field(default=10, env="DB_POOL_SIZE")
    database_max_overflow: int = Field(default=20, env="DB_MAX_OVERFLOW")
    database_pool_timeout: int = Field(default=30, env="DB_POOL_TIMEOUT")

    # Redis配置
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

    # Celery配置
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1", env="CELERY_BROKER_URL"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2", env="CELERY_RESULT_BACKEND"
    )

    # Reddit API配置
    reddit_client_id: Optional[str] = Field(default=None, env="REDDIT_CLIENT_ID")
    reddit_client_secret: Optional[str] = Field(
        default=None, env="REDDIT_CLIENT_SECRET"
    )
    reddit_user_agent: str = Field(
        default="RedditSignalScanner/0.1.0", env="REDDIT_USER_AGENT"
    )
    reddit_rate_limit: int = Field(default=60, env="REDDIT_RATE_LIMIT")

    # JWT配置 - 支持RS256/HS256双算法架构
    jwt_secret_key: str = Field(
        default="dev-secret-key-change-in-production", env="JWT_SECRET_KEY"
    )
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_algorithms: str = Field(
        default="RS256,HS256", env="JWT_ALGORITHMS"
    )  # 支持的算法列表
    jwt_access_token_expire_minutes: int = Field(
        default=1440, env="JWT_EXPIRE_MINUTES"
    )  # 24小时
    jwt_refresh_token_expire_days: int = Field(default=7, env="JWT_REFRESH_EXPIRE_DAYS")

    # RS256密钥配置
    jwt_private_key_path: Optional[str] = Field(
        default=None, env="JWT_PRIVATE_KEY_PATH"
    )
    jwt_public_key_path: Optional[str] = Field(default=None, env="JWT_PUBLIC_KEY_PATH")
    jwt_key_id: Optional[str] = Field(default="rss-key-1", env="JWT_KEY_ID")

    # 密钥轮换配置
    jwt_key_rotation_enabled: bool = Field(
        default=False, env="JWT_KEY_ROTATION_ENABLED"
    )
    jwt_key_rotation_days: int = Field(default=90, env="JWT_KEY_ROTATION_DAYS")

    # 文件上传配置
    upload_max_size: int = Field(default=10485760, env="UPLOAD_MAX_SIZE")  # 10MB
    upload_allowed_types: str = Field(
        default="text/plain,application/json", env="UPLOAD_ALLOWED_TYPES"
    )

    # 性能配置
    max_concurrent_tasks: int = Field(default=5, env="MAX_CONCURRENT_TASKS")
    analysis_timeout_seconds: int = Field(default=300, env="ANALYSIS_TIMEOUT")
    cache_ttl_seconds: int = Field(default=3600, env="CACHE_TTL")

    # 清理配置
    cleanup_interval_hours: int = Field(default=24, env="CLEANUP_INTERVAL")
    keep_completed_tasks_days: int = Field(default=30, env="KEEP_COMPLETED_DAYS")
    keep_failed_tasks_days: int = Field(default=7, env="KEEP_FAILED_DAYS")

    # 日志配置
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", env="LOG_FORMAT"
    )

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
    issues = []

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


def check_config_health() -> dict:
    """配置健康检查 - 诊断工具"""
    settings = get_settings()

    return {
        "environment": settings.environment,
        "debug_mode": settings.debug,
        "production_issues": validate_production_config(settings),
        "connectivity_issues": validate_config_connectivity(settings),
        "config_source": "environment" if os.getenv("DATABASE_URL") else "defaults",
    }
