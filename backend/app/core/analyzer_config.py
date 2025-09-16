"""
配置管理器 - Reddit Signal Scanner分析引擎
实现统一的配置访问和管理，支持动态参数调整

基于Linus设计原则：
- 单例模式保证全局配置一致性
- 点号分隔路径简化配置访问
- 类型安全的配置获取
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

import yaml

from .types import JsonValue


@dataclass
class StepConfig:
    """步骤配置类 - 每个分析步骤的专用配置

    兼容旧参数：enabled、params
    """

    step_name: str = "data_collection"
    max_duration: float = 60.0
    config_data: Optional[dict[str, JsonValue]] = None
    enabled: bool = True
    params: Optional[dict[str, JsonValue]] = None

    def __post_init__(self) -> None:
        if self.config_data is None:
            self.config_data = {}
        # 合并旧式 params 并落入统一 config_data
        if self.params:
            self.config_data.update(self.params)
        # 统一保存 enabled 标志
        self.config_data.setdefault("enabled", self.enabled)

    def get(self, key: str, default: Any = None) -> Any:
        """获取步骤配置值"""
        if self.config_data is None:
            return default
        return self.config_data.get(key, default)

    def __getattr__(self, name: str) -> Any:
        """支持属性访问方式"""
        if self.config_data is not None and name in self.config_data:
            return self.config_data[name]
        raise AttributeError(f"配置项 '{name}' 不存在")


class ConfigManager:
    """
    配置管理器 - 单例模式，全局配置访问

    功能：
    - 加载和缓存YAML配置文件
    - 支持点号分隔路径的配置访问
    - 提供步骤专用配置对象
    - 配置热重载（可选）
    """

    _instance: Optional["ConfigManager"] = None
    _config: dict[str, JsonValue] = {}
    _config_path: str = ""

    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load_config(self, config_path: str = "backend/config/analyzer.yaml") -> None:
        """
        加载配置文件

        Args:
            config_path: 配置文件路径，支持相对路径和绝对路径

        Raises:
            FileNotFoundError: 配置文件不存在
            yaml.YAMLError: YAML格式错误
        """
        # 处理相对路径
        if not Path(config_path).is_absolute():
            # 从项目根目录开始查找
            project_root = Path(__file__).parent.parent.parent.parent
            config_file = project_root / config_path
        else:
            config_file = Path(config_path)

        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_file}")

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
                self._config_path = str(config_file)
        except yaml.YAMLError as e:
            raise ValueError(f"配置文件格式错误: {e}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值 - 支持点号分隔的路径

        Args:
            key_path: 配置路径，如 'analysis_engine.community_discovery.max_duration'
            default: 默认值

        Returns:
            配置值或默认值

        Examples:
            >>> config.get('analysis_engine.version')
            'v2.1'
            >>> config.get('analysis_engine.community_discovery.max_communities')
            30
        """
        if not self._config:
            raise RuntimeError("配置尚未加载，请先调用 load_config()")

        keys = key_path.split(".")
        from typing import Any as _Any

        value: _Any = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def get_step_config(self, step_name: str) -> StepConfig:
        """
        获取步骤专用配置

        Args:
            step_name: 步骤名称，如 'community_discovery', 'data_collection'

        Returns:
            StepConfig对象，包含该步骤的所有配置
        """
        step_config_data = cast(
            dict[str, JsonValue], self.get(f"analysis_engine.{step_name}", {})
        )
        _md = step_config_data.get("max_duration", 60.0)
        max_duration = float(_md) if isinstance(_md, (int, float, str)) else 60.0

        return StepConfig(
            step_name=step_name, max_duration=max_duration, config_data=step_config_data
        )

    def reload_config(self) -> None:
        """重新加载配置文件 - 用于热重载"""
        if self._config_path:
            self.load_config(self._config_path)

    def get_all_step_names(self) -> List[str]:
        """获取所有配置的步骤名称"""
        engine_config = self.get("analysis_engine", {})
        return [
            key
            for key in engine_config.keys()
            if isinstance(engine_config[key], dict)
            and "max_duration" in engine_config[key]
        ]

    def validate_config(self) -> dict[str, JsonValue]:
        """
        验证配置完整性

        Returns:
            验证结果字典，包含错误和警告
        """
        errors = []
        warnings = []

        # 检查必需的配置项
        required_keys = [
            "analysis_engine.version",
            "analysis_engine.max_total_duration",
        ]

        for key in required_keys:
            if self.get(key) is None:
                errors.append(f"缺少必需配置项: {key}")

        # 检查步骤配置
        step_names = [
            "community_discovery",
            "data_collection",
            "signal_extraction",
            "result_ranking",
        ]
        for step_name in step_names:
            step_config = self.get(f"analysis_engine.{step_name}")
            if step_config is None:
                errors.append(f"缺少步骤配置: {step_name}")
            elif not isinstance(step_config.get("max_duration"), (int, float)):
                errors.append(f"步骤 {step_name} 缺少有效的 max_duration 配置")

        # 检查时间配置合理性
        total_max = self.get("analysis_engine.max_total_duration", 0)
        step_durations = sum(
            [self.get(f"analysis_engine.{step}.max_duration", 0) for step in step_names]
        )

        if step_durations > total_max:
            warnings.append(f"步骤总时长 {step_durations}s 超过总时长限制 {total_max}s")

        result: dict[str, JsonValue] = {
            "errors": cast(List[JsonValue], errors),
            "warnings": cast(List[JsonValue], warnings),
            "is_valid": len(errors) == 0,
        }
        return result


# 全局配置管理器实例
config_manager = ConfigManager()


def get_config() -> ConfigManager:
    """获取全局配置管理器实例"""
    return config_manager


def load_default_config() -> None:
    """加载默认配置 - 用于应用启动时"""
    try:
        config_manager.load_config()
        validation_result = config_manager.validate_config()

        if not validation_result["is_valid"]:
            raise ValueError(f"配置验证失败: {validation_result['errors']}")

        if validation_result.get("warnings"):
            import logging

            logger = logging.getLogger(__name__)
            from typing import cast as _cast

            warnings_list = _cast(list[str], validation_result.get("warnings", []))
            for warning in warnings_list:
                logger.warning(f"配置警告: {warning}")

    except Exception as e:
        raise RuntimeError(f"加载默认配置失败: {e}")


# 便捷函数
def get_step_config(step_name: str) -> StepConfig:
    """便捷函数 - 直接获取步骤配置"""
    return config_manager.get_step_config(step_name)


def get_config_value(key_path: str, default: Any = None) -> Any:
    """便捷函数 - 直接获取配置值"""
    return config_manager.get(key_path, default)
