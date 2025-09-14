"""
分析引擎性能自动调优服务

设计原则：
1. 简单规则引擎 - 避免过度智能化
2. 渐进式调整 - 小步快跑
3. 可观测性 - 每次调优都有记录
"""

import asyncio
import logging
import json
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple

from app.core.analyzer_metrics import (
    AnalysisPerformanceMetrics,
    get_metrics_collector,
)
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class TuningParameter(str, Enum):
    """可调优参数"""

    TIMEOUT_SECONDS = "timeout_seconds"
    COMMUNITY_COUNT = "community_count"
    BATCH_SIZE = "batch_size"
    CACHE_TTL = "cache_ttl"
    RETRY_COUNT = "retry_count"
    CONCURRENT_REQUESTS = "concurrent_requests"


@dataclass
class TuningConfig:
    """调优配置"""

    parameter: TuningParameter
    current_value: float
    min_value: float
    max_value: float
    step_size: float

    def can_increase(self) -> bool:
        """是否可以增加"""
        return self.current_value + self.step_size <= self.max_value

    def can_decrease(self) -> bool:
        """是否可以减少"""
        return self.current_value - self.step_size >= self.min_value

    def increase(self) -> float:
        """增加参数值"""
        new_value = min(self.current_value + self.step_size, self.max_value)
        self.current_value = new_value
        return new_value

    def decrease(self) -> float:
        """减少参数值"""
        new_value = max(self.current_value - self.step_size, self.min_value)
        self.current_value = new_value
        return new_value


class PerformanceTuner:
    """
    性能自动调优器

    调优策略：
    1. 基于滑动窗口的性能统计
    2. 简单阈值规则触发调优
    3. 小步调整，观察效果
    """

    def __init__(self) -> None:
        self.metrics_collector = get_metrics_collector()

        # 初始化调优配置
        self.configs: Dict[TuningParameter, TuningConfig] = {
            TuningParameter.TIMEOUT_SECONDS: TuningConfig(
                parameter=TuningParameter.TIMEOUT_SECONDS,
                current_value=300,  # 5分钟
                min_value=180,  # 3分钟
                max_value=600,  # 10分钟
                step_size=30,  # 30秒步长
            ),
            TuningParameter.COMMUNITY_COUNT: TuningConfig(
                parameter=TuningParameter.COMMUNITY_COUNT,
                current_value=10,
                min_value=5,
                max_value=20,
                step_size=2,
            ),
            TuningParameter.BATCH_SIZE: TuningConfig(
                parameter=TuningParameter.BATCH_SIZE,
                current_value=50,
                min_value=20,
                max_value=100,
                step_size=10,
            ),
            TuningParameter.CACHE_TTL: TuningConfig(
                parameter=TuningParameter.CACHE_TTL,
                current_value=3600,  # 1小时
                min_value=1800,  # 30分钟
                max_value=7200,  # 2小时
                step_size=600,  # 10分钟
            ),
            TuningParameter.RETRY_COUNT: TuningConfig(
                parameter=TuningParameter.RETRY_COUNT,
                current_value=3,
                min_value=1,
                max_value=5,
                step_size=1,
            ),
            TuningParameter.CONCURRENT_REQUESTS: TuningConfig(
                parameter=TuningParameter.CONCURRENT_REQUESTS,
                current_value=5,
                min_value=2,
                max_value=10,
                step_size=1,
            ),
        }

        # 调优历史
        self.tuning_history: List[Mapping[str, Any]] = []
        self.last_tuning_time: Dict[TuningParameter, datetime] = {}
        self.tuning_cooldown = timedelta(minutes=5)  # 冷却期

    async def analyze_and_tune(self) -> Mapping[str, Any]:
        """
        分析性能并执行调优

        返回调优动作和理由
        """
        tuning_actions = []

        # 获取最近的性能数据
        recent_metrics = await self._get_recent_metrics()
        if not recent_metrics:
            return {"status": "no_data", "actions": []}

        # 分析各项指标并调优

        # 1. 超时调优
        timeout_action = await self._tune_timeout(recent_metrics)
        if timeout_action:
            tuning_actions.append(timeout_action)

        # 2. 社区数量调优
        community_action = await self._tune_community_count(recent_metrics)
        if community_action:
            tuning_actions.append(community_action)

        # 3. 批量大小调优
        batch_action = await self._tune_batch_size(recent_metrics)
        if batch_action:
            tuning_actions.append(batch_action)

        # 4. 缓存TTL调优
        cache_action = await self._tune_cache_ttl(recent_metrics)
        if cache_action:
            tuning_actions.append(cache_action)

        # 5. 重试次数调优
        retry_action = await self._tune_retry_count(recent_metrics)
        if retry_action:
            tuning_actions.append(retry_action)

        # 应用调优
        for action in tuning_actions:
            await self._apply_tuning(action)

        return {
            "status": "tuned" if tuning_actions else "no_tuning_needed",
            "actions": tuning_actions,
            "current_configs": self._get_current_configs(),
        }

    async def _get_recent_metrics(self) -> List[AnalysisPerformanceMetrics]:
        """获取最近的性能指标（5分钟窗口）"""
        metrics = []

        # 从Redis获取最近完成的分析
        pattern = "analysis:complete:*"
        client = await get_redis_client()
        keys = await client.keys(pattern)
        for key in keys:
            try:
                data = await client.get(key)
                if data:
                    import json

                    metric_dict = data if isinstance(data, dict) else json.loads(data)
                    # 检查时间窗口
                    completed_raw = metric_dict.get("completed_at")
                    if not isinstance(completed_raw, str):
                        continue
                    completed_at = datetime.fromisoformat(completed_raw)
                    if datetime.utcnow() - completed_at < timedelta(minutes=5):
                        metrics.append(AnalysisPerformanceMetrics(**metric_dict))
            except (json.JSONDecodeError, TypeError, ValueError, KeyError) as e:
                logger.error(f"解析指标失败: {e}")
                continue

        return metrics

    async def _tune_timeout(
        self, metrics: List[AnalysisPerformanceMetrics]
    ) -> Optional[Mapping[str, Any]]:
        """超时参数调优"""

        param = TuningParameter.TIMEOUT_SECONDS

        # 检查冷却期
        if not self._can_tune(param):
            return None

        # 计算P90执行时间
        execution_times = [m.total_execution_time for m in metrics]
        if not execution_times:
            return None

        execution_times.sort()
        p90_index = int(len(execution_times) * 0.9)
        p90_time = (
            execution_times[p90_index]
            if p90_index < len(execution_times)
            else execution_times[-1]
        )

        config = self.configs[param]

        # 调优规则
        if p90_time > config.current_value * 0.8:  # P90接近超时
            if config.can_increase():
                new_value = config.increase()
                return {
                    "parameter": param.value,
                    "old_value": config.current_value - config.step_size,
                    "new_value": new_value,
                    "reason": f"P90执行时间({p90_time:.1f}s)接近超时阈值",
                    "confidence": 0.8,
                }
        elif p90_time < config.current_value * 0.5:  # 执行很快，可以减少超时
            if config.can_decrease():
                new_value = config.decrease()
                return {
                    "parameter": param.value,
                    "old_value": config.current_value + config.step_size,
                    "new_value": new_value,
                    "reason": f"P90执行时间({p90_time:.1f}s)远低于超时阈值",
                    "confidence": 0.6,
                }

        return None

    async def _tune_community_count(
        self, metrics: List[AnalysisPerformanceMetrics]
    ) -> Optional[Mapping[str, Any]]:
        """社区数量调优 - 基于缓存命中率"""

        param = TuningParameter.COMMUNITY_COUNT

        if not self._can_tune(param):
            return None

        # 计算平均缓存命中率
        cache_rates = [
            m.cache_hit_rate_overall for m in metrics if m.cache_hit_rate_overall > 0
        ]
        if not cache_rates:
            return None

        avg_cache_rate = sum(cache_rates) / len(cache_rates)
        config = self.configs[param]

        # 调优规则：缓存命中率低时减少社区数量，专注质量
        if avg_cache_rate < 60:  # 低于60%
            if config.can_decrease():
                new_value = config.decrease()
                return {
                    "parameter": param.value,
                    "old_value": config.current_value + config.step_size,
                    "new_value": new_value,
                    "reason": f"缓存命中率低({avg_cache_rate:.1f}%)，减少社区数量提高质量",
                    "confidence": 0.7,
                }
        elif avg_cache_rate > 80:  # 高于80%
            if config.can_increase():
                new_value = config.increase()
                return {
                    "parameter": param.value,
                    "old_value": config.current_value - config.step_size,
                    "new_value": new_value,
                    "reason": f"缓存命中率高({avg_cache_rate:.1f}%)，可以处理更多社区",
                    "confidence": 0.6,
                }

        return None

    async def _tune_batch_size(
        self, metrics: List[AnalysisPerformanceMetrics]
    ) -> Optional[Mapping[str, Any]]:
        """批量大小调优 - 基于内存使用"""

        param = TuningParameter.BATCH_SIZE

        if not self._can_tune(param):
            return None

        # 计算平均内存峰值
        memory_peaks = [m.peak_memory_mb for m in metrics if m.peak_memory_mb > 0]
        if not memory_peaks:
            return None

        avg_memory = sum(memory_peaks) / len(memory_peaks)
        config = self.configs[param]

        # 调优规则
        memory_limit = 1024  # 1GB限制

        if avg_memory > memory_limit * 0.8:  # 内存使用高
            if config.can_decrease():
                new_value = config.decrease()
                return {
                    "parameter": param.value,
                    "old_value": config.current_value + config.step_size,
                    "new_value": new_value,
                    "reason": f"内存使用高({avg_memory:.0f}MB)，减少批量大小",
                    "confidence": 0.8,
                }
        elif avg_memory < memory_limit * 0.4:  # 内存使用低
            if config.can_increase():
                new_value = config.increase()
                return {
                    "parameter": param.value,
                    "old_value": config.current_value - config.step_size,
                    "new_value": new_value,
                    "reason": f"内存使用低({avg_memory:.0f}MB)，增加批量大小提高效率",
                    "confidence": 0.5,
                }

        return None

    async def _tune_cache_ttl(
        self, metrics: List[AnalysisPerformanceMetrics]
    ) -> Optional[Mapping[str, Any]]:
        """缓存TTL调优"""

        param = TuningParameter.CACHE_TTL

        if not self._can_tune(param):
            return None

        # 基于缓存命中率和数据新鲜度需求调整
        cache_rates = [m.cache_hit_rate_overall for m in metrics]
        if not cache_rates:
            return None

        avg_cache_rate = sum(cache_rates) / len(cache_rates)
        config = self.configs[param]

        # 简单规则：命中率低时增加TTL
        if avg_cache_rate < 50:
            if config.can_increase():
                new_value = config.increase()
                return {
                    "parameter": param.value,
                    "old_value": config.current_value - config.step_size,
                    "new_value": new_value,
                    "reason": f"缓存命中率过低({avg_cache_rate:.1f}%)，增加TTL",
                    "confidence": 0.6,
                }

        return None

    async def _tune_retry_count(
        self, metrics: List[AnalysisPerformanceMetrics]
    ) -> Optional[Mapping[str, Any]]:
        """重试次数调优"""

        param = TuningParameter.RETRY_COUNT

        if not self._can_tune(param):
            return None

        # 计算API失败率
        total_calls = sum(m.api_calls_total for m in metrics)
        total_failed = sum(m.api_calls_failed for m in metrics)

        if total_calls == 0:
            return None

        failure_rate = (total_failed / total_calls) * 100
        config = self.configs[param]

        # 调优规则
        if failure_rate > 10:  # 失败率高于10%
            if config.can_increase():
                new_value = config.increase()
                return {
                    "parameter": param.value,
                    "old_value": config.current_value - config.step_size,
                    "new_value": new_value,
                    "reason": f"API失败率高({failure_rate:.1f}%)，增加重试次数",
                    "confidence": 0.7,
                }
        elif failure_rate < 2:  # 失败率很低
            if config.can_decrease():
                new_value = config.decrease()
                return {
                    "parameter": param.value,
                    "old_value": config.current_value + config.step_size,
                    "new_value": new_value,
                    "reason": f"API失败率低({failure_rate:.1f}%)，减少重试次数",
                    "confidence": 0.5,
                }

        return None

    def _can_tune(self, parameter: TuningParameter) -> bool:
        """检查是否可以调优（冷却期）"""
        if parameter not in self.last_tuning_time:
            return True

        time_since_last = datetime.utcnow() - self.last_tuning_time[parameter]
        return time_since_last > self.tuning_cooldown

    async def _apply_tuning(self, action: Mapping[str, Any]) -> None:
        """应用调优动作"""

        parameter = TuningParameter(action["parameter"])

        # 记录调优时间
        self.last_tuning_time[parameter] = datetime.utcnow()

        client = await get_redis_client()
        # 保存到Redis配置
        config_key = f"tuning:config:{parameter.value}"
        await client.set(config_key, str(action["new_value"]))

        # 记录调优历史
        self.tuning_history.append(
            {**dict(action), "applied_at": datetime.utcnow().isoformat()}
        )

        # 保存历史到Redis
        history_key = f"tuning:history:{datetime.utcnow().strftime('%Y%m%d')}"
        await client.lpush(history_key, dict(action))
        await client.expire(history_key, 86400 * 7)  # 保留7天

        logger.info(f"应用调优: {action}")

    def _get_current_configs(self) -> Mapping[str, float]:
        """获取当前配置值"""
        return {
            param.value: config.current_value for param, config in self.configs.items()
        }

    async def get_tuning_history(self, days: int = 1) -> List[Mapping[str, Any]]:
        """获取调优历史"""
        history = []

        for i in range(days):
            date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y%m%d")
            key = f"tuning:history:{date}"

            client = await get_redis_client()
            items = await client.lrange(key, 0, -1)
            for item in items:
                try:
                    import json
                    history.append(json.loads(item))
                except json.JSONDecodeError as e:
                    logger.warning("解析调优历史失败，已跳过", extra={"error": str(e)})

        return history

    async def get_config_value(self, parameter: TuningParameter) -> float:
        """获取参数当前值"""
        config_key = f"tuning:config:{parameter.value}"
        client = await get_redis_client()
        value = await client.get(config_key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError) as e:
                logger.warning("转换调优参数为浮点数失败，使用默认值", extra={"parameter": parameter.value, "value": value, "error": str(e)})
        return self.configs[parameter].current_value


# 全局实例
_tuner_instance: Optional[PerformanceTuner] = None


def get_performance_tuner() -> PerformanceTuner:
    """获取性能调优器单例"""
    global _tuner_instance
    if _tuner_instance is None:
        _tuner_instance = PerformanceTuner()
    return _tuner_instance
