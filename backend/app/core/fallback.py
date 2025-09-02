"""
Reddit Signal Scanner - SSE Fallback配置管理

Linus原则：
- 简单配置：一个类解决所有fallback配置需求
- 环境变量支持：生产环境可覆盖默认值
- 消除特殊情况：所有配置都有合理默认值
- 实用性优先：基于真实生产环境需求设计
"""

import threading
from typing import Any, Dict, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class FallbackConfig(BaseSettings):
    """SSE Fallback策略配置

    提供SSE连接失败时的HTTP轮询fallback配置，
    确保在任何网络环境下都能获取任务状态。
    """

    # 轮询建议间隔（毫秒）
    polling_interval_ms: int = Field(
        default=2000,
        description="客户端轮询建议间隔，2秒是用户体验和服务器负载的平衡点",
        ge=1000,  # 最少1秒
        le=10000,  # 最多10秒
    )

    # 快速轮询间隔（毫秒）- 任务刚开始时
    fast_polling_interval_ms: int = Field(
        default=1000, description="任务启动阶段的快速轮询间隔", ge=500, le=5000
    )

    # 慢速轮询间隔（毫秒）- 长时间运行的任务
    slow_polling_interval_ms: int = Field(
        default=5000, description="长时间运行任务的慢速轮询间隔", ge=3000, le=30000
    )

    # 任务超时配置（秒）
    task_timeout_seconds: int = Field(
        default=300,
        description="任务执行超时时间，5分钟适合大部分Reddit分析任务",
        ge=60,  # 最少1分钟
        le=1800,  # 最多30分钟
    )

    # 批量查询限制
    max_batch_size: int = Field(
        default=10, description="单次批量查询的最大任务数量", ge=1, le=50
    )

    # 进度估算参数
    estimated_duration_seconds: int = Field(
        default=300, description="标准任务预估时长，用于进度计算", ge=60, le=3600
    )

    # 重试配置
    max_retry_attempts: int = Field(
        default=3, description="API调用失败时的最大重试次数", ge=0, le=10
    )

    retry_backoff_seconds: float = Field(
        default=1.0, description="重试退避时间基数", ge=0.1, le=10.0
    )

    # 缓存配置
    status_cache_ttl_seconds: int = Field(
        default=30, description="状态查询结果缓存时间", ge=0, le=300  # 0表示禁用缓存
    )

    # 客户端指导配置
    connection_test_url: str = Field(
        default="/api/v1/health", description="客户端测试连接的URL"
    )

    sse_test_url: str = Field(
        default="/api/v1/stream/test-connection/test", description="SSE连接测试URL"
    )

    # 错误处理配置
    database_fallback_enabled: bool = Field(
        default=True, description="数据库连接失败时是否启用Mock fallback"
    )

    mock_fallback_duration_seconds: int = Field(
        default=60, description="Mock fallback的持续时间", ge=10, le=300
    )

    class Config:
        env_prefix = "FALLBACK_"
        env_file = ".env"


class ClientGuidance:
    """客户端轮询指导配置生成器

    根据任务状态和运行时间，为客户端提供智能的轮询策略建议。
    """

    def __init__(self, config: FallbackConfig):
        self.config = config

    def get_polling_guidance(
        self, task_status: str, runtime_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """获取轮询指导配置

        Args:
            task_status: 任务状态
            runtime_seconds: 任务已运行时间（秒）

        Returns:
            Dict: 轮询指导配置
        """
        if task_status in ("completed", "failed"):
            # 终态任务不需要轮询
            return {
                "should_poll": False,
                "reason": f"任务已{task_status}，无需继续轮询",
            }

        if task_status == "pending":
            # 待处理任务，快速轮询
            return {
                "should_poll": True,
                "interval_ms": self.config.fast_polling_interval_ms,
                "max_duration_seconds": 60,  # 1分钟后切换到正常轮询
                "reason": "任务等待处理中，建议快速轮询",
            }

        if task_status == "running":
            # 根据运行时间调整轮询间隔
            if runtime_seconds is None or runtime_seconds < 30:
                # 刚开始运行，快速轮询
                interval = self.config.fast_polling_interval_ms
                reason = "任务刚开始运行，建议快速轮询"
            elif runtime_seconds < 120:
                # 正常运行阶段
                interval = self.config.polling_interval_ms
                reason = "任务正常运行中"
            else:
                # 长时间运行，慢速轮询
                interval = self.config.slow_polling_interval_ms
                reason = "任务运行时间较长，建议慢速轮询"

            return {
                "should_poll": True,
                "interval_ms": interval,
                "timeout_seconds": self.config.task_timeout_seconds,
                "reason": reason,
            }

        # 未知状态，使用默认配置
        return {
            "should_poll": True,
            "interval_ms": self.config.polling_interval_ms,
            "reason": "未知状态，使用默认轮询间隔",
        }

    def get_retry_guidance(self, attempt_count: int) -> Dict[str, Any]:
        """获取重试指导配置

        Args:
            attempt_count: 当前重试次数

        Returns:
            Dict: 重试指导配置
        """
        if attempt_count >= self.config.max_retry_attempts:
            return {"should_retry": False, "reason": "已达到最大重试次数"}

        # 指数退避算法
        backoff_seconds = self.config.retry_backoff_seconds * (2**attempt_count)

        return {
            "should_retry": True,
            "delay_seconds": min(backoff_seconds, 30),  # 最大30秒
            "reason": f"第{attempt_count + 1}次重试，退避{backoff_seconds:.1f}秒",
        }

    def get_connection_test_guidance(self) -> Dict[str, str]:
        """获取连接测试指导

        Returns:
            Dict: 连接测试URL和说明
        """
        return {
            "health_check_url": self.config.connection_test_url,
            "sse_test_url": self.config.sse_test_url,
            "test_sequence": "建议先测试health_check，再测试sse_test",
            "fallback_trigger": "SSE测试失败时自动切换到HTTP轮询",
        }


# 全局配置实例（线程安全）
_fallback_config: Optional[FallbackConfig] = None
_client_guidance: Optional[ClientGuidance] = None
_config_lock = threading.Lock()


def get_fallback_config() -> FallbackConfig:
    """获取Fallback配置单例 - 线程安全版本

    Returns:
        FallbackConfig: 配置实例
    """
    global _fallback_config
    if _fallback_config is None:
        with _config_lock:
            # 双重检查锁定模式
            if _fallback_config is None:
                _fallback_config = FallbackConfig()
    return _fallback_config


def get_client_guidance() -> ClientGuidance:
    """获取客户端指导实例 - 线程安全版本

    Returns:
        ClientGuidance: 指导实例
    """
    global _client_guidance
    if _client_guidance is None:
        with _config_lock:
            # 双重检查锁定模式
            if _client_guidance is None:
                config = get_fallback_config()
                _client_guidance = ClientGuidance(config)
    return _client_guidance


# 便捷函数
def get_polling_interval(
    task_status: str, runtime_seconds: Optional[int] = None
) -> int:
    """获取建议的轮询间隔（毫秒）

    Args:
        task_status: 任务状态
        runtime_seconds: 运行时间

    Returns:
        int: 轮询间隔毫秒数，0表示不需要轮询
    """
    guidance = get_client_guidance()
    config = guidance.get_polling_guidance(task_status, runtime_seconds)
    return config.get("interval_ms", 0) if config.get("should_poll", False) else 0


def should_enable_fallback() -> bool:
    """检查是否应启用fallback模式

    Returns:
        bool: 是否启用fallback
    """
    config = get_fallback_config()
    return config.database_fallback_enabled


def get_batch_query_limit() -> int:
    """获取批量查询限制

    Returns:
        int: 最大批量查询数量
    """
    config = get_fallback_config()
    return config.max_batch_size


# 环境检测函数
def detect_client_environment() -> Dict[str, Any]:
    """检测客户端环境特征（用于服务端调试）

    Returns:
        Dict: 环境特征信息
    """
    return {
        "fallback_reasons": [
            "企业防火墙阻止WebSocket连接",
            "移动网络环境不稳定",
            "旧版浏览器不支持SSE",
            "代理服务器限制长连接",
            "客户端明确请求HTTP轮询",
        ],
        "detection_methods": [
            "User-Agent分析",
            "Connection header检查",
            "客户端显式fallback请求",
            "SSE连接测试失败",
        ],
        "optimization_tips": [
            "根据网络环境动态调整轮询间隔",
            "使用ETag和Last-Modified减少数据传输",
            "批量查询多个任务状态",
            "客户端智能缓存减少请求频率",
        ],
    }
