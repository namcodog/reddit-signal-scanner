"""
Celery配置加载和验证模块 - Reddit Signal Scanner
基于Linus设计原则：配置驱动架构，消除硬编码

核心功能：
- 从YAML配置文件加载Celery配置
- 环境变量覆盖支持
- 配置验证和默认值处理
- 统一的配置对象管理
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Optional, cast

import yaml

from .types import JsonValue

# 删除未使用的导入

logger = logging.getLogger(__name__)


@dataclass
class RedisConfig:
    """Redis连接配置"""

    broker_url: str = "redis://localhost:6379/0"
    result_backend_url: str = "redis://localhost:6379/0"
    broker_connection_retry_on_startup: bool = True
    broker_connection_max_retries: int = 3
    result_expires: int = 3600
    result_persistent: bool = True


@dataclass
class QueueConfig:
    """队列配置"""

    routing_key: str
    priority: int = 5
    max_length: int = 500


@dataclass
class WorkerConfig:
    """Worker进程配置"""

    prefetch_multiplier: int = 1
    acks_late: bool = True
    reject_on_worker_lost: bool = True
    timezone: str = "UTC"
    enable_utc: bool = True
    concurrency: int = 4
    max_tasks_per_child: int = 1000


@dataclass
class RetryConfig:
    """任务重试配置"""

    autoretry_for: List[str] = field(
        default_factory=lambda: [
            "sqlalchemy.exc.SQLAlchemyError",
            "redis.exceptions.ConnectionError",
            "requests.exceptions.RequestException",
        ]
    )
    max_retries: int = 3
    countdown: int = 60
    backoff: bool = True
    backoff_max: int = 600


@dataclass
class MonitoringConfig:
    """监控配置"""

    flower_port: int = 5555
    flower_basic_auth: List[str] = field(default_factory=lambda: ["admin:admin123"])
    flower_url_prefix: str = ""
    health_check_interval: int = 300
    task_stats_enable: bool = True
    task_stats_retention: int = 86400


@dataclass
class QueueOptimizationConfig:
    """队列性能优化配置 - Context7最佳实践"""

    # Context7推荐：队列优先级配置
    enable_priority_queues: bool = True
    default_max_priority: int = 10  # RabbitMQ x-max-priority
    high_priority_threshold: int = 8  # 高优先级阈值
    low_priority_threshold: int = 3  # 低优先级阈值

    # Context7推荐：队列分离策略
    enable_task_separation: bool = True
    long_running_queue: str = "analysis_queue"  # 长任务队列
    short_running_queue: str = "monitoring_queue"  # 短任务队列
    maintenance_queue: str = "cleanup_queue"  # 维护任务队列

    # Context7推荐：transient队列优化
    enable_transient_queues: bool = True
    transient_queue_pattern: str = "*_transient"  # transient队列模式
    transient_delivery_mode: int = 1  # 非持久化消息

    # Context7推荐：队列容量优化
    default_queue_max_length: int = 1000  # 默认队列最大长度
    high_priority_queue_max_length: int = 500  # 高优先级队列限制
    monitoring_queue_max_length: int = 200  # 监控队列限制

    # Context7推荐：路由优化配置
    enable_pattern_routing: bool = True
    auto_create_missing_queues: bool = True
    routing_key_ttl: int = 3600  # 路由键TTL（秒）


@dataclass
class SerializationOptimizationConfig:
    """序列化性能优化配置 - Context7最佳实践"""

    # Context7推荐：Pydantic集成优化
    pydantic_enabled: bool = True
    pydantic_strict_mode: bool = True
    pydantic_exclude_unset: bool = True

    # Context7推荐：序列化压缩优化
    task_compression: str = "gzip"  # Context7验证：减少网络传输
    result_compression: str = "gzip"
    compression_level: int = 6  # 平衡压缩率和CPU使用

    # Context7推荐：序列化性能优化
    task_serializer_buffer_size: int = 8192  # 8KB缓冲区
    result_serializer_buffer_size: int = 4096  # 4KB结果缓冲
    serialization_pool_size: int = 4  # 序列化线程池

    # Context7推荐：任务元数据优化
    include_task_metadata: bool = False  # 减少序列化开销
    optimize_for_size: bool = True  # 优先考虑传输大小
    eager_serialization: bool = True  # 立即序列化避免延迟


@dataclass
class CeleryConfig:
    """统一Celery配置对象"""

    redis: RedisConfig = field(default_factory=RedisConfig)
    queues: Dict[str, QueueConfig] = field(default_factory=dict)
    task_routes: Dict[str, str] = field(default_factory=dict)
    worker: WorkerConfig = field(default_factory=WorkerConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)

    # Context7优化：队列性能配置
    queue_optimization: QueueOptimizationConfig = field(
        default_factory=QueueOptimizationConfig
    )

    # Context7优化：扩展序列化配置
    serialization_optimization: SerializationOptimizationConfig = field(
        default_factory=SerializationOptimizationConfig
    )

    # 基础序列化配置 - Context7增强
    task_serializer: str = "json"
    result_serializer: str = "json"
    accept_content: List[str] = field(default_factory=lambda: ["json"])
    result_accept_content: List[str] = field(default_factory=lambda: ["json"])


class CeleryConfigLoader:
    """Celery配置加载器 - 实现配置驱动架构"""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """
        初始化配置加载器

        Args:
            config_path: YAML配置文件路径，默认为 backend/config/celery.yaml
        """
        self.config_path = (
            config_path
            or Path(__file__).parent.parent.parent / "config" / "celery.yaml"
        )
        self._config: Optional[CeleryConfig] = None

    def load_config(self) -> CeleryConfig:
        """
        加载并验证Celery配置

        Returns:
            CeleryConfig: 验证后的配置对象

        Raises:
            FileNotFoundError: 配置文件不存在
            yaml.YAMLError: YAML解析错误
            ValueError: 配置验证失败
        """
        if self._config is not None:
            return self._config

        logger.info("加载Celery配置: %s", self.config_path)

        # 加载YAML配置
        raw_config = self._load_yaml_config()

        # 环境变量替换
        raw_config = self._substitute_env_vars(raw_config)

        # 构建配置对象
        self._config = self._build_config_object(raw_config)

        # 验证配置
        self._validate_config(self._config)

        logger.info("Celery配置加载成功")
        return self._config

    def get_celery_settings(self) -> dict[str, JsonValue]:
        """
        获取Celery应用的配置字典

        Returns:
            Dict: Celery配置字典
        """
        config = self.load_config()

        # Context7队列优化：构建高性能队列配置
        queue_config = self._build_optimized_queue_config(config)

        # 构建任务路由
        task_routes = {}
        for pattern, queue_name in config.task_routes.items():
            task_routes[pattern] = {"queue": queue_name}

        # 返回Celery配置字典
        settings: dict[str, JsonValue] = {
            # Broker和Backend配置
            "broker_url": config.redis.broker_url,
            "result_backend": config.redis.result_backend_url,
            "broker_connection_retry_on_startup": (
                config.redis.broker_connection_retry_on_startup
            ),
            "broker_connection_max_retries": (
                config.redis.broker_connection_max_retries
            ),
            "result_expires": config.redis.result_expires,
            "result_persistent": config.redis.result_persistent,
            # Context7序列化优化配置
            "task_serializer": config.task_serializer,
            "result_serializer": config.result_serializer,
            "accept_content": cast(list[JsonValue], list(config.accept_content)),
            "result_accept_content": cast(
                list[JsonValue], list(config.result_accept_content)
            ),
            # Context7性能优化：压缩配置
            "task_compression": (config.serialization_optimization.task_compression),
            "result_compression": (
                config.serialization_optimization.result_compression
            ),
            # Context7性能优化：Pydantic集成
            "task_pydantic": (config.serialization_optimization.pydantic_enabled),
            "task_pydantic_strict": (
                config.serialization_optimization.pydantic_strict_mode
            ),
            # Context7性能优化：序列化缓冲优化
            "task_send_sent_event": (
                not config.serialization_optimization.include_task_metadata
            ),
            "worker_send_task_events": (
                config.serialization_optimization.include_task_metadata
            ),
            # 队列和路由配置
            "task_queues": cast(JsonValue, queue_config),
            "task_routes": cast(JsonValue, task_routes),
            # Worker配置
            "worker_prefetch_multiplier": config.worker.prefetch_multiplier,
            "task_acks_late": config.worker.acks_late,
            "task_reject_on_worker_lost": config.worker.reject_on_worker_lost,
            "timezone": config.worker.timezone,
            "enable_utc": config.worker.enable_utc,
            "worker_max_tasks_per_child": config.worker.max_tasks_per_child,
            # 默认重试配置（将被BaseTask覆盖）
            "task_default_max_retries": config.retry.max_retries,
            "task_default_retry_delay": config.retry.countdown,
        }
        # Context7队列优化：添加队列性能配置
        queue_settings = self._get_queue_optimization_settings(config)
        settings.update(queue_settings)

        return settings

    def _load_yaml_config(self) -> dict[str, Any]:
        """加载YAML配置文件"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                return cast(dict[str, Any], loaded) if isinstance(loaded, dict) else {}
        except FileNotFoundError:
            logger.error("Celery配置文件不存在: %s", self.config_path)
            raise
        except yaml.YAMLError as e:
            logger.error("YAML配置解析失败: %s", e)
            raise

    def _substitute_env_vars(self, config: dict[str, Any]) -> dict[str, Any]:
        """环境变量替换 - 支持 ${VAR:default} 语法"""

        def substitute_recursive(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: substitute_recursive(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [substitute_recursive(item) for item in obj]
            elif isinstance(obj, str) and "${" in obj:
                # 使用Template进行环境变量替换
                template = Template(obj)
                try:
                    return template.safe_substitute(os.environ)
                except KeyError as e:
                    logger.warning("环境变量未定义: %s", e)
                    return obj
            else:
                return obj

        return cast(dict[str, Any], substitute_recursive(config))

    def _build_optimized_queue_config(self, config: CeleryConfig) -> dict[str, Any]:
        """构建Context7优化的队列配置"""
        queue_config = {}
        queue_opt = config.queue_optimization

        # 基础队列配置
        for queue_name, queue_info in config.queues.items():
            queue_arguments: dict[str, Any] = {
                "x-max-length": queue_info.max_length,
            }

            # Context7优化：优先级队列支持
            if queue_opt.enable_priority_queues:
                queue_arguments["x-max-priority"] = queue_opt.default_max_priority

            queue_config[queue_name] = {
                "routing_key": queue_info.routing_key,
                "queue_arguments": queue_arguments,
            }

        # Context7优化：自动添加性能优化队列
        if not config.queues:  # 如果没有预定义队列，创建优化队列
            queue_config = self._create_default_optimized_queues(config)

        return queue_config

    def _create_default_optimized_queues(self, config: CeleryConfig) -> dict[str, Any]:
        """创建Context7优化的默认队列配置"""
        queue_opt = config.queue_optimization

        return {
            # 高优先级分析队列 - Context7长任务优化
            "analysis_queue": {
                "routing_key": "analysis.#",
                "queue_arguments": {
                    "x-max-priority": queue_opt.default_max_priority,
                    "x-max-length": queue_opt.default_queue_max_length,
                    "x-message-ttl": 3600000,  # 1小时TTL
                },
            },
            # 快速监控队列 - Context7短任务优化
            "monitoring_queue": {
                "routing_key": "monitoring.#",
                "queue_arguments": {
                    "x-max-priority": queue_opt.default_max_priority,
                    "x-max-length": queue_opt.monitoring_queue_max_length,
                    "x-message-ttl": 300000,  # 5分钟TTL
                },
            },
            # 清理维护队列 - Context7维护任务优化
            "cleanup_queue": {
                "routing_key": "cleanup.#",
                "queue_arguments": {
                    "x-max-priority": queue_opt.low_priority_threshold,
                    "x-max-length": 100,  # 较小容量
                },
            },
        }

    def _get_queue_optimization_settings(
        self, config: CeleryConfig
    ) -> dict[str, JsonValue]:
        """获取Context7队列优化设置"""
        queue_opt = config.queue_optimization

        optimization_settings: dict[str, JsonValue] = {
            # Context7队列优化：基础配置
            "task_create_missing_queues": (queue_opt.auto_create_missing_queues),
            "task_queue_max_priority": queue_opt.default_max_priority,
            "task_default_priority": queue_opt.low_priority_threshold,
            # Context7队列优化：路由优化
            "task_inherit_parent_priority": True,
            "task_queue_ha_policy": "all",  # RabbitMQ高可用
            # Context7队列优化：性能调优
            "worker_prefetch_multiplier": 1,  # 避免任务堆积
            "task_acks_late": True,  # 任务完成后确认
            "worker_max_tasks_per_child": 1000,  # 防止内存泄漏
        }

        # Context7队列优化：任务路由规则
        if queue_opt.enable_pattern_routing:
            task_routes = {
                # 分析任务路由到analysis队列（高优先级）
                "app.tasks.analysis_tasks.*": {
                    "queue": queue_opt.long_running_queue,
                    "priority": queue_opt.high_priority_threshold,
                },
                # 监控任务路由到monitoring队列（中优先级）
                "app.tasks.monitoring.*": {
                    "queue": queue_opt.short_running_queue,
                    "priority": queue_opt.default_max_priority // 2,
                },
                # 清理任务路由到cleanup队列（低优先级）
                "app.tasks.data_cleanup.*": {
                    "queue": queue_opt.maintenance_queue,
                    "priority": queue_opt.low_priority_threshold,
                },
                # 通用任务默认路由
                "*": {
                    "queue": "analysis_queue",
                    "priority": queue_opt.low_priority_threshold + 1,
                },
            }
            optimization_settings["task_routes"] = cast(JsonValue, task_routes)

        return optimization_settings

    def _build_config_object(self, raw_config: dict[str, Any]) -> CeleryConfig:
        """构建配置对象"""
        config = CeleryConfig()

        # Redis配置
        if "redis" in raw_config:
            redis_data = raw_config["redis"]
            config.redis = RedisConfig(
                broker_url=redis_data.get("broker_url", config.redis.broker_url),
                result_backend_url=redis_data.get(
                    "result_backend_url", config.redis.result_backend_url
                ),
                broker_connection_retry_on_startup=redis_data.get(
                    "broker_connection_retry_on_startup", True
                ),
                broker_connection_max_retries=redis_data.get(
                    "broker_connection_max_retries", 3
                ),
                result_expires=redis_data.get("result_expires", 3600),
                result_persistent=redis_data.get("result_persistent", True),
            )

        # 队列配置
        if "queues" in raw_config:
            for queue_name, queue_data in raw_config["queues"].items():
                config.queues[queue_name] = QueueConfig(
                    routing_key=queue_data["routing_key"],
                    priority=queue_data.get("priority", 5),
                    max_length=queue_data.get("max_length", 500),
                )

        # 任务路由配置
        if "task_routes" in raw_config:
            config.task_routes = raw_config["task_routes"]

        # Worker配置
        if "worker" in raw_config:
            worker_data = raw_config["worker"]
            config.worker = WorkerConfig(
                prefetch_multiplier=worker_data.get("prefetch_multiplier", 1),
                acks_late=worker_data.get("acks_late", True),
                reject_on_worker_lost=worker_data.get("reject_on_worker_lost", True),
                timezone=worker_data.get("timezone", "UTC"),
                enable_utc=worker_data.get("enable_utc", True),
                concurrency=worker_data.get("concurrency", 4),
                max_tasks_per_child=worker_data.get("max_tasks_per_child", 1000),
            )

        # 重试配置
        if "retry" in raw_config:
            retry_data = raw_config["retry"]
            config.retry = RetryConfig(
                autoretry_for=retry_data.get(
                    "autoretry_for", config.retry.autoretry_for
                ),
                max_retries=retry_data.get("max_retries", 3),
                countdown=retry_data.get("countdown", 60),
                backoff=retry_data.get("backoff", True),
                backoff_max=retry_data.get("backoff_max", 600),
            )

        # 监控配置
        if "monitoring" in raw_config and "flower" in raw_config["monitoring"]:
            flower_data = raw_config["monitoring"]["flower"]
            config.monitoring = MonitoringConfig(
                flower_port=flower_data.get("port", 5555),
                flower_basic_auth=flower_data.get("basic_auth", ["admin:admin123"]),
                flower_url_prefix=flower_data.get("url_prefix", ""),
            )

        # Context7序列化优化配置
        if "serialization" in raw_config:
            serial_data = raw_config["serialization"]
            config.task_serializer = serial_data.get("task_serializer", "json")
            config.result_serializer = serial_data.get("result_serializer", "json")
            config.accept_content = serial_data.get("accept_content", ["json"])
            config.result_accept_content = serial_data.get(
                "result_accept_content", ["json"]
            )

            # Context7队列性能优化配置
            if "queue_optimization" in raw_config:
                queue_opt_data = raw_config["queue_optimization"]
                config.queue_optimization = QueueOptimizationConfig(
                    enable_priority_queues=queue_opt_data.get(
                        "enable_priority_queues", True
                    ),
                    default_max_priority=queue_opt_data.get("default_max_priority", 10),
                    high_priority_threshold=queue_opt_data.get(
                        "high_priority_threshold", 8
                    ),
                    low_priority_threshold=queue_opt_data.get(
                        "low_priority_threshold", 3
                    ),
                    enable_task_separation=queue_opt_data.get(
                        "enable_task_separation", True
                    ),
                    long_running_queue=queue_opt_data.get(
                        "long_running_queue", "analysis_queue"
                    ),
                    short_running_queue=queue_opt_data.get(
                        "short_running_queue", "monitoring_queue"
                    ),
                    maintenance_queue=queue_opt_data.get(
                        "maintenance_queue", "cleanup_queue"
                    ),
                    enable_transient_queues=queue_opt_data.get(
                        "enable_transient_queues", True
                    ),
                    transient_queue_pattern=queue_opt_data.get(
                        "transient_queue_pattern", "*_transient"
                    ),
                    transient_delivery_mode=queue_opt_data.get(
                        "transient_delivery_mode", 1
                    ),
                    default_queue_max_length=queue_opt_data.get(
                        "default_queue_max_length", 1000
                    ),
                    high_priority_queue_max_length=queue_opt_data.get(
                        "high_priority_queue_max_length", 500
                    ),
                    monitoring_queue_max_length=queue_opt_data.get(
                        "monitoring_queue_max_length", 200
                    ),
                    enable_pattern_routing=queue_opt_data.get(
                        "enable_pattern_routing", True
                    ),
                    auto_create_missing_queues=queue_opt_data.get(
                        "auto_create_missing_queues", True
                    ),
                    routing_key_ttl=queue_opt_data.get("routing_key_ttl", 3600),
                )

            # Context7序列化性能优化配置
            if "optimization" in serial_data:
                opt_data = serial_data["optimization"]
                config.serialization_optimization = SerializationOptimizationConfig(
                    pydantic_enabled=opt_data.get("pydantic_enabled", True),
                    pydantic_strict_mode=opt_data.get("pydantic_strict_mode", True),
                    pydantic_exclude_unset=opt_data.get("pydantic_exclude_unset", True),
                    task_compression=opt_data.get("task_compression", "gzip"),
                    result_compression=opt_data.get("result_compression", "gzip"),
                    compression_level=opt_data.get("compression_level", 6),
                    task_serializer_buffer_size=opt_data.get(
                        "task_serializer_buffer_size", 8192
                    ),
                    result_serializer_buffer_size=opt_data.get(
                        "result_serializer_buffer_size", 4096
                    ),
                    serialization_pool_size=opt_data.get("serialization_pool_size", 4),
                    include_task_metadata=opt_data.get("include_task_metadata", False),
                    optimize_for_size=opt_data.get("optimize_for_size", True),
                    eager_serialization=opt_data.get("eager_serialization", True),
                )

        return config

    def _validate_config(self, config: CeleryConfig) -> None:
        """验证配置有效性"""
        # 验证Redis连接配置
        if not config.redis.broker_url:
            raise ValueError("broker_url不能为空")
        if not config.redis.result_backend_url:
            raise ValueError("result_backend_url不能为空")

        # 验证队列配置
        if not config.queues:
            logger.warning("未定义任务队列，将使用默认队列")

        # 验证任务路由
        if not config.task_routes:
            logger.warning("未定义任务路由，所有任务将进入默认队列")

        # 验证重试配置
        if config.retry.max_retries < 0:
            raise ValueError("max_retries不能为负数")
        if config.retry.countdown < 0:
            raise ValueError("countdown不能为负数")

        # Context7队列优化验证
        queue_opt = config.queue_optimization
        if queue_opt.default_max_priority < 1 or queue_opt.default_max_priority > 255:
            logger.warning(
                "default_max_priority应在1-255之间，当前值: %d",
                queue_opt.default_max_priority,
            )

        if queue_opt.high_priority_threshold <= queue_opt.low_priority_threshold:
            logger.warning(
                "high_priority_threshold应大于low_priority_threshold，" "当前: %d <= %d",
                queue_opt.high_priority_threshold,
                queue_opt.low_priority_threshold,
            )

        if queue_opt.default_queue_max_length < 100:
            logger.warning(
                "default_queue_max_length建议不少于100，当前: %d",
                queue_opt.default_queue_max_length,
            )

        # Context7序列化优化验证
        serialization_opt = config.serialization_optimization
        if (
            serialization_opt.compression_level < 1
            or serialization_opt.compression_level > 9
        ):
            logger.warning(
                "compression_level应在1-9之间，当前值: %d",
                serialization_opt.compression_level,
            )

        if serialization_opt.task_serializer_buffer_size < 1024:
            logger.warning(
                "task_serializer_buffer_size建议不少于1KB，当前: %d",
                serialization_opt.task_serializer_buffer_size,
            )

        # Context7推荐：验证Pydantic配置一致性
        if serialization_opt.pydantic_enabled and config.task_serializer not in [
            "json",
            "msgpack",
        ]:
            logger.warning(
                "Pydantic优化建议使用json或msgpack序列化器，当前: %s",
                config.task_serializer,
            )

        logger.debug("Context7队列和序列化优化配置验证通过")


# 全局配置加载器实例
_config_loader = CeleryConfigLoader()


def get_celery_config() -> CeleryConfig:
    """获取Celery配置对象"""
    return _config_loader.load_config()


def get_celery_settings() -> dict[str, JsonValue]:
    """获取Celery应用配置字典"""
    return _config_loader.get_celery_settings()


def reload_config() -> CeleryConfig:
    """重新加载配置"""
    _config_loader._config = None
    return _config_loader.load_config()
