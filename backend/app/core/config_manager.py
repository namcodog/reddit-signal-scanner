"""
Reddit Signal Scanner - 统一配置管理器

PRD-03 系统配置的中心化管理
基于Linus设计原则：配置即代码、版本控制、类型安全
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from decimal import Decimal
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """缓存配置"""

    # Redis配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_max_connections: int = 20

    # 缓存策略
    default_ttl_seconds: int = 3600  # 1小时
    max_cache_size_mb: int = 512
    cleanup_batch_size: int = 100
    cache_hit_threshold: float = 0.7  # 缓存新鲜度阈值

    # 缓存预热
    warmup_enabled: bool = True
    warmup_communities: List[str] = field(
        default_factory=lambda: ["r/startups", "r/entrepreneur", "r/smallbusiness"]
    )


@dataclass
class APIConfig:
    """API配置"""

    # Reddit API配置
    reddit_base_url: str = "https://www.reddit.com"
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    reddit_user_agent: str = "RedditSignalScanner/1.0 by cache_first_architecture"

    # 速率限制配置
    requests_per_minute: int = 20  # PRD-03要求：远低于60限制
    burst_limit: int = 5
    request_timeout_seconds: int = 30

    # 重试配置
    max_retries: int = 3
    retry_delay_seconds: int = 2
    backoff_factor: float = 1.5


@dataclass
class DataCollectionConfig:
    """数据采集配置"""

    # 采集策略
    max_posts_per_community: int = 100
    max_concurrent_requests: int = 10
    collection_timeout_seconds: int = 300  # 5分钟

    # 缓存优先配置
    cache_priority_threshold: float = 0.9  # 90%缓存优先
    api_fallback_enabled: bool = True
    max_api_calls_per_batch: int = 15

    # 数据质量
    min_post_score: int = 1
    min_post_length: int = 50
    max_post_age_hours: int = 24
    exclude_deleted_posts: bool = True
    exclude_removed_posts: bool = True


@dataclass
class DatabaseConfig:
    """数据库配置"""

    # PostgreSQL配置
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "reddit_scanner"
    postgres_user: str = "postgres"
    postgres_password: Optional[str] = None

    # 连接池配置
    pool_size: int = 20
    max_overflow: int = 30
    pool_timeout: int = 30
    pool_recycle: int = 3600


@dataclass
class SecurityConfig:
    """安全配置"""

    # 输入验证
    max_community_name_length: int = 50
    max_communities_count: int = 100
    max_content_length: int = 10000

    # 速率限制
    user_requests_per_minute: int = 60
    ip_requests_per_minute: int = 300

    # 会话配置
    session_timeout_minutes: int = 30
    jwt_secret_key: Optional[str] = None
    jwt_algorithm: str = "HS256"


@dataclass
class LoggingConfig:
    """日志配置"""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_enabled: bool = True
    file_path: str = "logs/reddit_scanner.log"
    file_max_size_mb: int = 50
    file_backup_count: int = 5

    # 结构化日志
    structured_logging: bool = True
    include_trace_id: bool = True


@dataclass
class MonitoringConfig:
    """监控配置"""

    # 性能监控
    enable_metrics: bool = True
    metrics_port: int = 9090

    # 健康检查
    health_check_enabled: bool = True
    health_check_interval_seconds: int = 30

    # 告警配置
    alert_enabled: bool = True
    alert_webhooks: List[str] = field(default_factory=list)


class SystemConfig:
    """系统配置管理器

    统一管理所有系统配置，支持：
    - 环境变量覆盖
    - 配置文件加载
    - 类型验证
    - 配置热更新
    """

    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self._cache_config: Optional[CacheConfig] = None
        self._api_config: Optional[APIConfig] = None
        self._data_collection_config: Optional[DataCollectionConfig] = None
        self._database_config: Optional[DatabaseConfig] = None
        self._security_config: Optional[SecurityConfig] = None
        self._logging_config: Optional[LoggingConfig] = None
        self._monitoring_config: Optional[MonitoringConfig] = None

    @property
    def cache(self) -> CacheConfig:
        """缓存配置"""
        if self._cache_config is None:
            self._cache_config = self._load_cache_config()
        return self._cache_config

    @property
    def api(self) -> APIConfig:
        """API配置"""
        if self._api_config is None:
            self._api_config = self._load_api_config()
        return self._api_config

    @property
    def data_collection(self) -> DataCollectionConfig:
        """数据采集配置"""
        if self._data_collection_config is None:
            self._data_collection_config = self._load_data_collection_config()
        return self._data_collection_config

    @property
    def database(self) -> DatabaseConfig:
        """数据库配置"""
        if self._database_config is None:
            self._database_config = self._load_database_config()
        return self._database_config

    @property
    def security(self) -> SecurityConfig:
        """安全配置"""
        if self._security_config is None:
            self._security_config = self._load_security_config()
        return self._security_config

    @property
    def logging(self) -> LoggingConfig:
        """日志配置"""
        if self._logging_config is None:
            self._logging_config = self._load_logging_config()
        return self._logging_config

    @property
    def monitoring(self) -> MonitoringConfig:
        """监控配置"""
        if self._monitoring_config is None:
            self._monitoring_config = self._load_monitoring_config()
        return self._monitoring_config

    def reload_config(self):
        """重新加载配置"""
        self._cache_config = None
        self._api_config = None
        self._data_collection_config = None
        self._database_config = None
        self._security_config = None
        self._logging_config = None
        self._monitoring_config = None
        logger.info("配置已重新加载")

    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要（隐藏敏感信息）"""
        return {
            "cache": {
                "ttl_seconds": self.cache.default_ttl_seconds,
                "max_size_mb": self.cache.max_cache_size_mb,
                "hit_threshold": self.cache.cache_hit_threshold,
            },
            "api": {
                "requests_per_minute": self.api.requests_per_minute,
                "timeout_seconds": self.api.request_timeout_seconds,
                "max_retries": self.api.max_retries,
            },
            "data_collection": {
                "max_posts_per_community": self.data_collection.max_posts_per_community,
                "cache_priority": self.data_collection.cache_priority_threshold,
                "timeout_seconds": self.data_collection.collection_timeout_seconds,
            },
            "security": {
                "max_communities": self.security.max_communities_count,
                "requests_per_minute": self.security.user_requests_per_minute,
            },
        }

    # 私有配置加载方法

    def _load_cache_config(self) -> CacheConfig:
        """加载缓存配置"""
        return CacheConfig(
            redis_host=self._get_env("REDIS_HOST", "localhost"),
            redis_port=int(self._get_env("REDIS_PORT", "6379")),
            redis_db=int(self._get_env("REDIS_DB", "0")),
            redis_password=self._get_env("REDIS_PASSWORD"),
            redis_max_connections=int(self._get_env("REDIS_MAX_CONNECTIONS", "20")),
            default_ttl_seconds=int(self._get_env("CACHE_DEFAULT_TTL", "3600")),
            max_cache_size_mb=int(self._get_env("CACHE_MAX_SIZE_MB", "512")),
            cleanup_batch_size=int(self._get_env("CACHE_CLEANUP_BATCH_SIZE", "100")),
            cache_hit_threshold=float(self._get_env("CACHE_HIT_THRESHOLD", "0.7")),
        )

    def _load_api_config(self) -> APIConfig:
        """加载API配置"""
        return APIConfig(
            reddit_client_id=self._get_env("REDDIT_CLIENT_ID"),
            reddit_client_secret=self._get_env("REDDIT_CLIENT_SECRET"),
            requests_per_minute=int(self._get_env("API_REQUESTS_PER_MINUTE", "20")),
            burst_limit=int(self._get_env("API_BURST_LIMIT", "5")),
            request_timeout_seconds=int(self._get_env("API_TIMEOUT", "30")),
            max_retries=int(self._get_env("API_MAX_RETRIES", "3")),
            retry_delay_seconds=int(self._get_env("API_RETRY_DELAY", "2")),
            backoff_factor=float(self._get_env("API_BACKOFF_FACTOR", "1.5")),
        )

    def _load_data_collection_config(self) -> DataCollectionConfig:
        """加载数据采集配置"""
        return DataCollectionConfig(
            max_posts_per_community=int(
                self._get_env("MAX_POSTS_PER_COMMUNITY", "100")
            ),
            max_concurrent_requests=int(self._get_env("MAX_CONCURRENT_REQUESTS", "10")),
            collection_timeout_seconds=int(self._get_env("COLLECTION_TIMEOUT", "300")),
            cache_priority_threshold=float(
                self._get_env("CACHE_PRIORITY_THRESHOLD", "0.9")
            ),
            api_fallback_enabled=self._get_env("API_FALLBACK_ENABLED", "true").lower()
            == "true",
            max_api_calls_per_batch=int(self._get_env("MAX_API_CALLS_PER_BATCH", "15")),
            min_post_score=int(self._get_env("MIN_POST_SCORE", "1")),
            min_post_length=int(self._get_env("MIN_POST_LENGTH", "50")),
            max_post_age_hours=int(self._get_env("MAX_POST_AGE_HOURS", "24")),
        )

    def _load_database_config(self) -> DatabaseConfig:
        """加载数据库配置"""
        return DatabaseConfig(
            postgres_host=self._get_env("POSTGRES_HOST", "localhost"),
            postgres_port=int(self._get_env("POSTGRES_PORT", "5432")),
            postgres_db=self._get_env("POSTGRES_DB", "reddit_scanner"),
            postgres_user=self._get_env("POSTGRES_USER", "postgres"),
            postgres_password=self._get_env("POSTGRES_PASSWORD"),
            pool_size=int(self._get_env("DB_POOL_SIZE", "20")),
            max_overflow=int(self._get_env("DB_MAX_OVERFLOW", "30")),
            pool_timeout=int(self._get_env("DB_POOL_TIMEOUT", "30")),
        )

    def _load_security_config(self) -> SecurityConfig:
        """加载安全配置"""
        return SecurityConfig(
            max_community_name_length=int(
                self._get_env("MAX_COMMUNITY_NAME_LENGTH", "50")
            ),
            max_communities_count=int(self._get_env("MAX_COMMUNITIES_COUNT", "100")),
            max_content_length=int(self._get_env("MAX_CONTENT_LENGTH", "10000")),
            user_requests_per_minute=int(
                self._get_env("USER_REQUESTS_PER_MINUTE", "60")
            ),
            ip_requests_per_minute=int(self._get_env("IP_REQUESTS_PER_MINUTE", "300")),
            jwt_secret_key=self._get_env("JWT_SECRET_KEY"),
            jwt_algorithm=self._get_env("JWT_ALGORITHM", "HS256"),
        )

    def _load_logging_config(self) -> LoggingConfig:
        """加载日志配置"""
        return LoggingConfig(
            level=self._get_env("LOG_LEVEL", "INFO"),
            file_enabled=self._get_env("LOG_FILE_ENABLED", "true").lower() == "true",
            file_path=self._get_env("LOG_FILE_PATH", "logs/reddit_scanner.log"),
            file_max_size_mb=int(self._get_env("LOG_FILE_MAX_SIZE_MB", "50")),
            structured_logging=self._get_env("STRUCTURED_LOGGING", "true").lower()
            == "true",
        )

    def _load_monitoring_config(self) -> MonitoringConfig:
        """加载监控配置"""
        return MonitoringConfig(
            enable_metrics=self._get_env("ENABLE_METRICS", "true").lower() == "true",
            metrics_port=int(self._get_env("METRICS_PORT", "9090")),
            health_check_enabled=self._get_env("HEALTH_CHECK_ENABLED", "true").lower()
            == "true",
            health_check_interval_seconds=int(
                self._get_env("HEALTH_CHECK_INTERVAL", "30")
            ),
            alert_enabled=self._get_env("ALERT_ENABLED", "true").lower() == "true",
        )

    def _get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """获取环境变量"""
        return os.getenv(key, default)


# 全局配置实例
_system_config: Optional[SystemConfig] = None


def get_system_config() -> SystemConfig:
    """获取系统配置单例"""
    global _system_config
    if _system_config is None:
        _system_config = SystemConfig()
    return _system_config


def reload_system_config():
    """重新加载系统配置"""
    global _system_config
    if _system_config:
        _system_config.reload_config()
    else:
        _system_config = SystemConfig()


# 便捷访问函数
def get_cache_config() -> CacheConfig:
    """获取缓存配置"""
    return get_system_config().cache


def get_api_config() -> APIConfig:
    """获取API配置"""
    return get_system_config().api


def get_data_collection_config() -> DataCollectionConfig:
    """获取数据采集配置"""
    return get_system_config().data_collection
