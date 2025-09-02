"""
Celery配置加载和验证模块 - Reddit Signal Scanner
基于Linus设计原则：配置驱动架构，消除硬编码

核心功能：
- 从YAML配置文件加载Celery配置
- 环境变量覆盖支持
- 配置验证和默认值处理
- 统一的配置对象管理
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from string import Template

import yaml

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
class CeleryConfig:
    """统一Celery配置对象"""

    redis: RedisConfig = field(default_factory=RedisConfig)
    queues: Dict[str, QueueConfig] = field(default_factory=dict)
    task_routes: Dict[str, str] = field(default_factory=dict)
    worker: WorkerConfig = field(default_factory=WorkerConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)

    # 序列化配置
    task_serializer: str = "json"
    result_serializer: str = "json"
    accept_content: List[str] = field(default_factory=lambda: ["json"])
    result_accept_content: List[str] = field(default_factory=lambda: ["json"])


class CeleryConfigLoader:
    """Celery配置加载器 - 实现配置驱动架构"""

    def __init__(self, config_path: Optional[Path] = None):
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

        logger.info(f"加载Celery配置: {self.config_path}")

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

    def get_celery_settings(self) -> Dict[str, Any]:
        """
        获取Celery应用的配置字典

        Returns:
            Dict: Celery配置字典
        """
        config = self.load_config()

        # 构建队列配置
        queue_config = {}
        for queue_name, queue_info in config.queues.items():
            queue_config[queue_name] = {
                "routing_key": queue_info.routing_key,
                "queue_arguments": {
                    "x-max-priority": queue_info.priority,
                    "x-max-length": queue_info.max_length,
                },
            }

        # 构建任务路由
        task_routes = {}
        for pattern, queue_name in config.task_routes.items():
            task_routes[pattern] = {"queue": queue_name}

        # 返回Celery配置字典
        return {
            # Broker和Backend配置
            "broker_url": config.redis.broker_url,
            "result_backend": config.redis.result_backend_url,
            "broker_connection_retry_on_startup": (
                config.redis.broker_connection_retry_on_startup
            ),
            "broker_connection_max_retries": config.redis.broker_connection_max_retries,
            "result_expires": config.redis.result_expires,
            "result_persistent": config.redis.result_persistent,
            # 序列化配置
            "task_serializer": config.task_serializer,
            "result_serializer": config.result_serializer,
            "accept_content": config.accept_content,
            "result_accept_content": config.result_accept_content,
            # 队列和路由配置
            "task_queues": queue_config,
            "task_routes": task_routes,
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

    def _load_yaml_config(self) -> Dict[str, Any]:
        """加载YAML配置文件"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.error(f"Celery配置文件不存在: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"YAML配置解析失败: {e}")
            raise

    def _substitute_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
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
                    logger.warning(f"环境变量未定义: {e}")
                    return obj
            else:
                return obj

        return substitute_recursive(config)

    def _build_config_object(self, raw_config: Dict[str, Any]) -> CeleryConfig:
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

        # 序列化配置
        if "serialization" in raw_config:
            serial_data = raw_config["serialization"]
            config.task_serializer = serial_data.get("task_serializer", "json")
            config.result_serializer = serial_data.get("result_serializer", "json")
            config.accept_content = serial_data.get("accept_content", ["json"])
            config.result_accept_content = serial_data.get(
                "result_accept_content", ["json"]
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

        logger.debug("配置验证通过")


# 全局配置加载器实例
_config_loader = CeleryConfigLoader()


def get_celery_config() -> CeleryConfig:
    """获取Celery配置对象"""
    return _config_loader.load_config()


def get_celery_settings() -> Dict[str, Any]:
    """获取Celery应用配置字典"""
    return _config_loader.get_celery_settings()


def reload_config() -> CeleryConfig:
    """重新加载配置"""
    _config_loader._config = None
    return _config_loader.load_config()
