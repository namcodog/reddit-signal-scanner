"""
扩缩容配置管理器

支持：
- YAML配置文件加载和保存
- 配置验证和类型检查
- 默认配置管理
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

import yaml

from .load_balancer import LoadBalancingStrategy
from .load_monitor import LoadThresholds
from .types import JsonValue
from .worker_scaler import ScalingConfig

_logger = logging.getLogger(__name__)


@dataclass
class MonitoringConfig:
    """监控配置"""

    check_interval: int = 30
    queue_thresholds: Dict[str, int] = field(default_factory=dict)
    cpu_high_threshold: float = 80.0
    cpu_critical_threshold: float = 90.0
    memory_high_threshold: float = 85.0
    memory_critical_threshold: float = 95.0
    worker_timeout: int = 120


@dataclass
class LoadBalancingConfig:
    """负载均衡配置"""

    strategy: LoadBalancingStrategy = LoadBalancingStrategy.LEAST_CONNECTIONS
    rebalance_interval: int = 60
    worker_weights: Dict[str, int] = field(default_factory=dict)


@dataclass
class NotificationConfig:
    """通知配置"""

    enabled: bool = False
    events: List[str] = field(default_factory=list)
    log_enabled: bool = True
    log_level: str = "INFO"


@dataclass
class ScalingConfigFile:
    """完整的扩缩容配置文件结构"""

    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    autoscaling: ScalingConfig = field(default_factory=ScalingConfig)
    load_balancing: LoadBalancingConfig = field(default_factory=LoadBalancingConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    advanced: Dict[str, JsonValue] = field(default_factory=dict)


class ScalingConfigManager:
    """扩缩容配置管理器"""

    def __init__(self, config_path: Optional[str] = None) -> None:
        """初始化配置管理器"""
        self.config_path = Path(
            config_path
            or os.environ.get("SCALING_CONFIG_PATH")
            or "config/scaling.yaml"
        )
        self.config: ScalingConfigFile = ScalingConfigFile()
        self.change_callbacks: List[Callable[[ScalingConfigFile], None]] = []

    def load_config(self) -> ScalingConfigFile:
        """加载配置文件"""
        try:
            if not self.config_path.exists():
                _logger.warning("配置文件不存在，使用默认配置: %s", self.config_path)
                return self._get_default_config()

            with open(self.config_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)

            if not yaml_data:
                _logger.warning("配置文件为空，使用默认配置")
                return self._get_default_config()

            config = self._parse_config_data(yaml_data)
            self.config = config

            _logger.info("配置文件加载成功: %s", self.config_path)
            return config

        except Exception as e:
            _logger.error("加载配置文件失败: %s", e)
            return self._get_default_config()

    def save_config(self, config: ScalingConfigFile) -> bool:
        """保存配置文件"""
        try:
            # 确保目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # 转换为字典
            config_dict = self._config_to_dict(config)

            # 写入YAML文件
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    config_dict,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    indent=2,
                )

            self.config = config
            _logger.info("配置文件保存成功: %s", self.config_path)

            # 通知配置变更
            self._notify_config_change(config)

            return True

        except Exception as e:
            _logger.error("保存配置文件失败: %s", e)
            return False

    def reload_config(self) -> ScalingConfigFile:
        """重新加载配置文件"""
        config = self.load_config()
        self._notify_config_change(config)
        return config

    def add_change_callback(
        self, callback: Callable[[ScalingConfigFile], None]
    ) -> None:
        """添加配置变更回调"""
        self.change_callbacks.append(callback)

    def remove_change_callback(
        self, callback: Callable[[ScalingConfigFile], None]
    ) -> None:
        """移除配置变更回调"""
        if callback in self.change_callbacks:
            self.change_callbacks.remove(callback)

    def get_load_thresholds(self) -> LoadThresholds:
        """获取负载阈值配置"""
        mon_config = self.config.monitoring
        return LoadThresholds(
            queue_high_threshold=(
                max(mon_config.queue_thresholds.values())
                if mon_config.queue_thresholds
                else 50
            ),
            queue_critical_threshold=(
                max(mon_config.queue_thresholds.values()) * 2
                if mon_config.queue_thresholds
                else 100
            ),
            cpu_high_threshold=mon_config.cpu_high_threshold,
            cpu_critical_threshold=mon_config.cpu_critical_threshold,
            memory_high_threshold=mon_config.memory_high_threshold,
            memory_critical_threshold=mon_config.memory_critical_threshold,
            worker_timeout_seconds=mon_config.worker_timeout,
        )

    def get_scaling_config(self) -> ScalingConfig:
        """获取扩缩容配置"""
        return self.config.autoscaling

    def get_load_balancing_strategy(self) -> LoadBalancingStrategy:
        """获取负载均衡策略"""
        return self.config.load_balancing.strategy

    def update_worker_weights(self, weights: Dict[str, int]) -> None:
        """更新Worker权重配置"""
        self.config.load_balancing.worker_weights.update(weights)
        self.save_config(self.config)

    def _get_default_config(self) -> ScalingConfigFile:
        """获取默认配置"""
        return ScalingConfigFile(
            monitoring=MonitoringConfig(
                queue_thresholds={
                    "analysis_queue": 50,
                    "maintenance_queue": 20,
                    "cleanup_queue": 15,
                    "monitoring_queue": 10,
                }
            ),
            autoscaling=ScalingConfig(
                target_queues=[
                    "analysis_queue",
                    "maintenance_queue",
                    "cleanup_queue",
                    "monitoring_queue",
                ]
            ),
        )

    def _parse_config_data(self, data: Mapping[str, Any]) -> ScalingConfigFile:
        """解析配置数据"""
        config = ScalingConfigFile()

        # 解析监控配置
        if "monitoring" in data:
            mon_data = data["monitoring"]
            config.monitoring = MonitoringConfig(
                check_interval=mon_data.get("check_interval", 30),
                queue_thresholds=mon_data.get("queue_thresholds", {}),
                cpu_high_threshold=mon_data.get("cpu_high_threshold", 80.0),
                cpu_critical_threshold=mon_data.get("cpu_critical_threshold", 90.0),
                memory_high_threshold=mon_data.get("memory_high_threshold", 85.0),
                memory_critical_threshold=mon_data.get(
                    "memory_critical_threshold", 95.0
                ),
                worker_timeout=mon_data.get("worker_timeout", 120),
            )

        # 解析扩缩容配置
        if "autoscaling" in data:
            auto_data = data["autoscaling"]
            config.autoscaling = ScalingConfig(
                min_workers=auto_data.get("min_workers", 2),
                max_workers=auto_data.get("max_workers", 10),
                scale_up_threshold=auto_data.get("scale_up_threshold", 0.8),
                scale_down_threshold=auto_data.get("scale_down_threshold", 0.3),
                cooldown_seconds=auto_data.get("cooldown_seconds", 300),
                scale_up_step=auto_data.get("scale_up_step", 2),
                scale_down_step=auto_data.get("scale_down_step", 1),
                target_queues=auto_data.get("target_queues"),
            )

        # 解析负载均衡配置
        if "load_balancing" in data:
            lb_data = data["load_balancing"]
            strategy_str = lb_data.get("strategy", "least_connections")

            try:
                strategy = LoadBalancingStrategy(strategy_str)
            except ValueError:
                _logger.warning("无效的负载均衡策略: %s，使用默认策略", strategy_str)
                strategy = LoadBalancingStrategy.LEAST_CONNECTIONS

            config.load_balancing = LoadBalancingConfig(
                strategy=strategy,
                rebalance_interval=lb_data.get("rebalance_interval", 60),
                worker_weights=lb_data.get("worker_weights", {}),
            )

        # 解析通知配置
        if "notifications" in data:
            notif_data = data["notifications"]
            config.notifications = NotificationConfig(
                enabled=notif_data.get("enabled", False),
                events=notif_data.get("events", []),
                log_enabled=notif_data.get("log", {}).get("enabled", True),
                log_level=notif_data.get("log", {}).get("level", "INFO"),
            )

        # 解析高级配置
        if "advanced" in data:
            config.advanced = data["advanced"]

        return config

    def _config_to_dict(self, config: ScalingConfigFile) -> Dict[str, Any]:
        """将配置对象转换为字典"""
        return {
            "monitoring": {
                "check_interval": config.monitoring.check_interval,
                "queue_thresholds": config.monitoring.queue_thresholds,
                "cpu_high_threshold": config.monitoring.cpu_high_threshold,
                "cpu_critical_threshold": (config.monitoring.cpu_critical_threshold),
                "memory_high_threshold": (config.monitoring.memory_high_threshold),
                "memory_critical_threshold": config.monitoring.memory_critical_threshold,
                "worker_timeout": config.monitoring.worker_timeout,
            },
            "autoscaling": {
                "enabled": True,
                "min_workers": config.autoscaling.min_workers,
                "max_workers": config.autoscaling.max_workers,
                "scale_up_threshold": config.autoscaling.scale_up_threshold,
                "scale_down_threshold": config.autoscaling.scale_down_threshold,
                "cooldown_seconds": config.autoscaling.cooldown_seconds,
                "scale_up_step": config.autoscaling.scale_up_step,
                "scale_down_step": config.autoscaling.scale_down_step,
                "target_queues": config.autoscaling.target_queues,
            },
            "load_balancing": {
                "strategy": config.load_balancing.strategy.value,
                "rebalance_interval": config.load_balancing.rebalance_interval,
                "worker_weights": config.load_balancing.worker_weights,
            },
            "notifications": {
                "enabled": config.notifications.enabled,
                "events": config.notifications.events,
                "log": {
                    "enabled": config.notifications.log_enabled,
                    "level": config.notifications.log_level,
                },
            },
            "advanced": config.advanced,
        }

    def _notify_config_change(self, config: ScalingConfigFile) -> None:
        """通知配置变更"""
        for callback in self.change_callbacks:
            try:
                callback(config)
            except Exception as e:
                _logger.error("配置变更回调失败: %s", e)


# 全局配置管理器实例
_config_manager: Optional[ScalingConfigManager] = None


def get_scaling_config_manager() -> ScalingConfigManager:
    """获取扩缩容配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ScalingConfigManager()
        _config_manager.load_config()
    return _config_manager
