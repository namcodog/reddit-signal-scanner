"""
兼容桥接：历史代码从 app.core.config_manager 导入 settings
当前统一配置在 app.core.config 中提供 get_settings()
"""

from .config import get_settings

# 向后兼容的全局 settings 引用
settings = get_settings()

__all__ = ["settings", "get_settings"]

"""
Reddit Signal Scanner - 统一配置管理器 (类型安全重构版)

PRD-03 系统配置的中心化管理
基于Linus设计原则：配置即代码、版本控制、类型安全

类型安全升级：
- 使用safe_env_* 函数消除union-attr错误
- 环境变量获取永不返回None
- 明确的类型转换和错误处理
"""

import logging
import os
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

# 导入类型安全的环境变量函数
from .types import (
    ConfigError,
    JsonValue,
    safe_env_bool,
    safe_env_get,
    safe_env_int,
)

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

    # API限制配置
    rate_limit_requests_per_minute: int = 60
    rate_limit_burst_size: int = 10
    timeout_seconds: int = 30
    retry_attempts: int = 3
    retry_backoff_seconds: float = 1.5

    # 批处理配置
    max_posts_per_request: int = 100
    max_comments_per_request: int = 500
    batch_size: int = 25


@dataclass
class CrawlerConfig:
    """爬虫配置"""

    # 爬虫策略
    max_concurrent_communities: int = 5
    crawl_interval_minutes: int = 15
    posts_per_community: int = 100
    enable_comments: bool = True
    max_comment_depth: int = 3

    # 内容过滤
    min_post_score: int = 1
    min_post_length: int = 50
    max_post_age_hours: int = 24
    spam_score_threshold: float = 0.8

    # 优先级调度
    high_priority_communities: List[str] = field(
        default_factory=lambda: ["r/startups", "r/entrepreneur"]
    )
    low_priority_communities: List[str] = field(
        default_factory=lambda: ["r/test", "r/sandbox"]
    )


@dataclass
class DatabaseConfig:
    """数据库配置"""

    # 基础连接配置
    host: str = "localhost"
    port: int = 5432
    database: str = "reddit_signal_scanner"
    username: str = "postgres"
    password: Optional[str] = None

    # 连接池配置
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout_seconds: int = 30
    pool_recycle_seconds: int = 3600

    # 查询配置
    query_timeout_seconds: int = 30
    slow_query_threshold_ms: int = 1000


@dataclass
class SystemConfig:
    """系统级配置管理"""

    def __init__(self) -> None:
        """初始化系统配置 - 类型安全版"""
        try:
            self.cache = self._load_cache_config()
            self.api = self._load_api_config()
            self.crawler = self._load_crawler_config()
            self.database = self._load_database_config()
            self.monitoring = self._load_monitoring_config()

            logger.info("系统配置加载完成 - 类型安全版")
        except ConfigError as e:
            logger.error(f"配置加载失败: {e}")
            raise
        except Exception as e:
            logger.error(f"配置系统初始化失败: {e}")
            raise ConfigError(f"配置初始化错误: {str(e)}")

    def _load_cache_config(self) -> CacheConfig:
        """加载缓存配置 - 类型安全版"""
        return CacheConfig(
            redis_host=safe_env_get("REDIS_HOST", "localhost"),
            redis_port=safe_env_int("REDIS_PORT", 6379),
            redis_db=safe_env_int("REDIS_DB", 0),
            redis_password=os.getenv("REDIS_PASSWORD"),  # 可以为None
            redis_max_connections=safe_env_int("REDIS_MAX_CONNECTIONS", 20),
            default_ttl_seconds=safe_env_int("DEFAULT_TTL_SECONDS", 3600),
            max_cache_size_mb=safe_env_int("MAX_CACHE_SIZE_MB", 512),
            cleanup_batch_size=safe_env_int("CLEANUP_BATCH_SIZE", 100),
            cache_hit_threshold=float(safe_env_get("CACHE_HIT_THRESHOLD", "0.7")),
            warmup_enabled=safe_env_bool("CACHE_WARMUP_ENABLED", True),
        )

    def _load_api_config(self) -> APIConfig:
        """加载API配置 - 类型安全版"""
        return APIConfig(
            reddit_base_url=safe_env_get("REDDIT_BASE_URL", "https://www.reddit.com"),
            reddit_client_id=os.getenv("REDDIT_CLIENT_ID"),  # 可以为None
            reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET"),  # 可以为None
            reddit_user_agent=safe_env_get(
                "REDDIT_USER_AGENT",
                "RedditSignalScanner/1.0 by cache_first_architecture",
            ),
            rate_limit_requests_per_minute=safe_env_int("RATE_LIMIT_RPM", 60),
            rate_limit_burst_size=safe_env_int("RATE_LIMIT_BURST", 10),
            timeout_seconds=safe_env_int("API_TIMEOUT", 30),
            retry_attempts=safe_env_int("API_RETRY_ATTEMPTS", 3),
            retry_backoff_seconds=float(safe_env_get("API_RETRY_BACKOFF", "1.5")),
            max_posts_per_request=safe_env_int("MAX_POSTS_PER_REQUEST", 100),
            max_comments_per_request=safe_env_int("MAX_COMMENTS_PER_REQUEST", 500),
            batch_size=safe_env_int("API_BATCH_SIZE", 25),
        )

    def _load_crawler_config(self) -> CrawlerConfig:
        """加载爬虫配置 - 类型安全版"""
        return CrawlerConfig(
            max_concurrent_communities=safe_env_int("MAX_CONCURRENT_COMMUNITIES", 5),
            crawl_interval_minutes=safe_env_int("CRAWL_INTERVAL_MINUTES", 15),
            posts_per_community=safe_env_int("POSTS_PER_COMMUNITY", 100),
            enable_comments=safe_env_bool("ENABLE_COMMENTS", True),
            max_comment_depth=safe_env_int("MAX_COMMENT_DEPTH", 3),
            min_post_score=safe_env_int("MIN_POST_SCORE", 1),
            min_post_length=safe_env_int("MIN_POST_LENGTH", 50),
            max_post_age_hours=safe_env_int("MAX_POST_AGE_HOURS", 24),
            spam_score_threshold=float(safe_env_get("SPAM_SCORE_THRESHOLD", "0.8")),
        )

    def _load_database_config(self) -> DatabaseConfig:
        """加载数据库配置 - 类型安全版"""
        return DatabaseConfig(
            host=safe_env_get("DATABASE_HOST", "localhost"),
            port=safe_env_int("DATABASE_PORT", 5432),
            database=safe_env_get("DATABASE_NAME", "reddit_signal_scanner"),
            username=safe_env_get("DATABASE_USER", "postgres"),
            password=os.getenv("DATABASE_PASSWORD"),  # 可以为None
            pool_size=safe_env_int("DATABASE_POOL_SIZE", 10),
            max_overflow=safe_env_int("DATABASE_MAX_OVERFLOW", 20),
            pool_timeout_seconds=safe_env_int("DATABASE_POOL_TIMEOUT", 30),
            pool_recycle_seconds=safe_env_int("DATABASE_POOL_RECYCLE", 3600),
            query_timeout_seconds=safe_env_int("DATABASE_QUERY_TIMEOUT", 30),
            slow_query_threshold_ms=safe_env_int("DATABASE_SLOW_QUERY_THRESHOLD", 1000),
        )

    def _load_monitoring_config(self) -> dict[str, JsonValue]:
        """加载监控配置 - 类型安全版"""
        return {
            "enable_metrics": safe_env_bool("ENABLE_METRICS", True),
            "metrics_port": safe_env_int("METRICS_PORT", 9090),
            "health_check_enabled": safe_env_bool("HEALTH_CHECK_ENABLED", True),
            "health_check_interval_seconds": safe_env_int("HEALTH_CHECK_INTERVAL", 30),
            "alert_enabled": safe_env_bool("ALERT_ENABLED", True),
        }

    def get_redis_url(self) -> str:
        """获取Redis连接URL - 类型安全版"""
        password_part = (
            f":{self.cache.redis_password}@" if self.cache.redis_password else ""
        )
        return f"redis://{password_part}{self.cache.redis_host}:{self.cache.redis_port}/{self.cache.redis_db}"

    def get_database_url(self) -> str:
        """获取数据库连接URL - 类型安全版"""
        password_part = f":{self.database.password}" if self.database.password else ""
        return (
            f"postgresql://{self.database.username}{password_part}@"
            f"{self.database.host}:{self.database.port}/{self.database.database}"
        )

    def validate_config(self) -> bool:
        """验证配置完整性 - 类型安全版

        Returns:
            bool: 配置是否有效

        Raises:
            ConfigError: 配置验证失败
        """
        try:
            # 验证必要的配置项
            required_configs = [
                (self.cache.redis_host, "Redis主机地址"),
                (self.database.host, "数据库主机地址"),
                (self.database.database, "数据库名称"),
            ]

            for value, name in required_configs:
                if not value:
                    raise ConfigError(f"{name}不能为空")

            # 验证数值配置的合理性
            if self.cache.redis_port <= 0 or self.cache.redis_port > 65535:
                raise ConfigError(f"Redis端口号无效: {self.cache.redis_port}")

            if self.database.port <= 0 or self.database.port > 65535:
                raise ConfigError(f"数据库端口号无效: {self.database.port}")

            if self.crawler.max_concurrent_communities <= 0:
                raise ConfigError(
                    f"并发爬虫数量必须大于0: {self.crawler.max_concurrent_communities}"
                )

            logger.info("配置验证通过")
            return True

        except Exception as e:
            logger.error(f"配置验证失败: {e}")
            raise ConfigError(f"配置验证错误: {str(e)}")


# 全局配置实例 - 类型安全版
_system_config: Optional[SystemConfig] = None


def get_system_config() -> SystemConfig:
    """获取全局系统配置实例 - 类型安全版

    Returns:
        SystemConfig: 系统配置对象

    Raises:
        ConfigError: 配置初始化失败
    """
    global _system_config

    if _system_config is None:
        try:
            _system_config = SystemConfig()
            _system_config.validate_config()
        except Exception as e:
            logger.error(f"系统配置初始化失败: {e}")
            raise ConfigError(f"无法初始化系统配置: {str(e)}")

    return _system_config


def reload_config() -> SystemConfig:
    """重新加载配置 - 类型安全版

    Returns:
        SystemConfig: 新的系统配置对象

    Raises:
        ConfigError: 配置重载失败
    """
    global _system_config

    try:
        _system_config = None  # 清除旧配置
        new_config = get_system_config()
        logger.info("配置重新加载成功")
        return new_config
    except Exception as e:
        logger.error(f"配置重载失败: {e}")
        raise ConfigError(f"配置重载错误: {str(e)}")


def get_config_summary() -> dict[str, JsonValue]:
    """获取配置摘要 - 用于诊断和监控

    Returns:
        dict[str, JsonValue]: 配置摘要（不包含敏感信息）
    """
    try:
        config = get_system_config()

        return {
            "cache": {
                "redis_host": config.cache.redis_host,
                "redis_port": config.cache.redis_port,
                "redis_db": config.cache.redis_db,
                "has_password": bool(config.cache.redis_password),
                "max_connections": config.cache.redis_max_connections,
            },
            "database": {
                "host": config.database.host,
                "port": config.database.port,
                "database": config.database.database,
                "username": config.database.username,
                "has_password": bool(config.database.password),
                "pool_size": config.database.pool_size,
            },
            "crawler": {
                "max_concurrent": config.crawler.max_concurrent_communities,
                "crawl_interval": config.crawler.crawl_interval_minutes,
                "posts_per_community": config.crawler.posts_per_community,
            },
            "monitoring": config.monitoring,
        }
    except Exception as e:
        logger.error(f"获取配置摘要失败: {e}")
        return {"error": str(e)}


# 兼容旧接口：提供采集与缓存配置的便捷获取函数
def get_data_collection_config() -> CrawlerConfig:
    """兼容层：返回采集/爬虫相关配置。"""
    return get_system_config().crawler


def get_cache_config() -> CacheConfig:
    """兼容层：返回缓存相关配置。"""
    return get_system_config().cache
