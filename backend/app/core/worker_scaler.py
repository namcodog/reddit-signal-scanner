"""
动态Worker扩缩容控制器

基于Celery control.autoscale实现Worker动态扩缩容，支持：
- 基于负载的自动扩缩容
- 配置驱动的阈值控制
- 冷却时间防止频繁调整
- 最小/最大Worker数量限制
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

from celery import Celery

from .celery_app import get_celery_app
from .load_monitor import LoadLevel, LoadMetrics, LoadMonitor, get_load_monitor
from .types import JsonValue

_logger = logging.getLogger(__name__)


class ScalingAction(Enum):
    """扩缩容动作枚举"""

    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_CHANGE = "no_change"


@dataclass
class ScalingConfig:
    """扩缩容配置"""

    min_workers: int = 2
    max_workers: int = 10
    scale_up_threshold: float = 0.8
    scale_down_threshold: float = 0.3
    cooldown_seconds: int = 300
    scale_up_step: int = 2
    scale_down_step: int = 1
    target_queues: Optional[List[str]] = None

    def __post_init__(self) -> None:
        """初始化后处理"""
        if self.target_queues is None:
            self.target_queues = [
                "analysis_queue",
                "maintenance_queue",
                "cleanup_queue",
                "monitoring_queue",
            ]


@dataclass
class ScalingHistory:
    """扩缩容历史记录"""

    timestamp: datetime
    action: ScalingAction
    from_count: int
    to_count: int
    reason: str
    success: bool


class WorkerScaler:
    """Worker动态扩缩容控制器"""

    def __init__(
        self,
        celery_app: Optional[Celery] = None,
        load_monitor: Optional[LoadMonitor] = None,
        config: Optional[ScalingConfig] = None,
    ) -> None:
        """初始化扩缩容控制器"""
        self.celery = celery_app or get_celery_app()
        self.load_monitor = load_monitor or get_load_monitor()
        self.config = config or ScalingConfig()
        self.last_scaling_time: Optional[datetime] = None
        self.current_worker_count = self.config.min_workers
        self.scaling_history: List[ScalingHistory] = []
        self._scaling_active = False

    async def start_auto_scaling(self) -> None:
        """启动自动扩缩容"""
        if self._scaling_active:
            _logger.warning("自动扩缩容已在运行")
            return

        self._scaling_active = True
        _logger.info("启动自动扩缩容控制器")

        # 启动负载监控
        await self.load_monitor.start_monitoring()

        # 启动扩缩容循环
        asyncio.create_task(self._auto_scale_loop())

    async def stop_auto_scaling(self) -> None:
        """停止自动扩缩容"""
        if not self._scaling_active:
            return

        self._scaling_active = False
        _logger.info("停止自动扩缩容控制器")

        # 停止负载监控
        await self.load_monitor.stop_monitoring()

    async def scale_up(self, target_count: Optional[int] = None) -> bool:
        """手动扩容Worker"""
        if target_count is None:
            target_count = min(
                self.current_worker_count + self.config.scale_up_step,
                self.config.max_workers,
            )

        if target_count <= self.current_worker_count:
            _logger.warning(
                "目标Worker数 %d 不大于当前数量 %d，跳过扩容",
                target_count,
                self.current_worker_count,
            )
            return False

        if target_count > self.config.max_workers:
            target_count = self.config.max_workers

        return await self._execute_scaling(
            ScalingAction.SCALE_UP,
            target_count,
            "手动扩容请求",
        )

    async def scale_down(self, target_count: Optional[int] = None) -> bool:
        """手动缩容Worker"""
        if target_count is None:
            target_count = max(
                self.current_worker_count - self.config.scale_down_step,
                self.config.min_workers,
            )

        if target_count >= self.current_worker_count:
            _logger.warning(
                "目标Worker数 %d 不小于当前数量 %d，跳过缩容",
                target_count,
                self.current_worker_count,
            )
            return False

        if target_count < self.config.min_workers:
            target_count = self.config.min_workers

        return await self._execute_scaling(
            ScalingAction.SCALE_DOWN,
            target_count,
            "手动缩容请求",
        )

    async def get_scaling_status(self) -> Dict[str, JsonValue]:
        """获取扩缩容状态"""
        current_load = await self.load_monitor.get_current_load()

        return {
            "active": self._scaling_active,
            "current_workers": self.current_worker_count,
            "min_workers": self.config.min_workers,
            "max_workers": self.config.max_workers,
            "last_scaling_time": (
                self.last_scaling_time.isoformat() if self.last_scaling_time else None
            ),
            "cooldown_remaining": self._get_cooldown_remaining(),
            "load_level": current_load.load_level.value,
            "recent_history": [
                {
                    "timestamp": h.timestamp.isoformat(),
                    "action": h.action.value,
                    "from_count": h.from_count,
                    "to_count": h.to_count,
                    "reason": h.reason,
                    "success": h.success,
                }
                for h in self.scaling_history[-5:]  # 最近5条记录
            ],
        }

    def _is_in_cooldown(self) -> bool:
        """检查是否在冷却期间"""
        if not self.last_scaling_time:
            return False

        cooldown_end = self.last_scaling_time + timedelta(
            seconds=self.config.cooldown_seconds
        )
        return datetime.now() < cooldown_end

    def _get_cooldown_remaining(self) -> int:
        """获取剩余冷却时间（秒）"""
        if not self.last_scaling_time:
            return 0

        cooldown_end = self.last_scaling_time + timedelta(
            seconds=self.config.cooldown_seconds
        )
        remaining = cooldown_end - datetime.now()
        return max(0, int(remaining.total_seconds()))

    def _should_scale_up(self, metrics: LoadMetrics) -> bool:
        """判断是否应该扩容"""
        # 检查是否已达到最大Worker数
        if self.current_worker_count >= self.config.max_workers:
            return False

        # 检查负载级别
        if metrics.load_level in (LoadLevel.HIGH, LoadLevel.CRITICAL):
            return True

        # 检查队列长度
        target_queues = self.config.target_queues or []
        total_queue_length = sum(
            queue.length
            for queue_name, queue in metrics.queue_metrics.items()
            if queue_name in target_queues
        )

        if total_queue_length > 0:
            # 计算平均每个Worker的任务数
            avg_tasks_per_worker = total_queue_length / max(metrics.online_workers, 1)

            # 如果平均任务数超过阈值，则扩容
            if avg_tasks_per_worker > 10:  # 可配置的阈值
                return True

        return False

    def _should_scale_down(self, metrics: LoadMetrics) -> bool:
        """判断是否应该缩容"""
        # 检查是否已达到最小Worker数
        if self.current_worker_count <= self.config.min_workers:
            return False

        # 检查负载级别
        if metrics.load_level == LoadLevel.LOW:
            # 检查队列是否都很空
            target_queues = self.config.target_queues or []
            total_queue_length = sum(
                queue.length
                for queue_name, queue in metrics.queue_metrics.items()
                if queue_name in target_queues
            )

            # 如果总队列长度很小且活跃任务很少，考虑缩容
            if total_queue_length < 5 and metrics.total_active_tasks < 3:
                return True

        return False

    async def _execute_scaling(
        self,
        action: ScalingAction,
        target_count: int,
        reason: str,
    ) -> bool:
        """执行扩缩容操作"""
        from_count = self.current_worker_count
        success = False

        try:
            # 使用Celery control.autoscale进行扩缩容
            result = self.celery.control.autoscale(
                max=target_count,
                min=max(1, target_count - 2),  # 最小值稍小于最大值
                destination=None,  # 对所有worker生效
            )

            if result:
                success = True
                self.current_worker_count = target_count
                self.last_scaling_time = datetime.now()

                action_str = "扩容" if action == ScalingAction.SCALE_UP else "缩容"
                _logger.info(
                    "%s成功: %d -> %d workers, 原因: %s",
                    action_str,
                    from_count,
                    target_count,
                    reason,
                )
            else:
                _logger.error("扩缩容失败: control.autoscale返回空结果")

        except Exception as e:
            _logger.error("执行扩缩容失败: %s", e)

        # 记录历史
        history = ScalingHistory(
            timestamp=datetime.now(),
            action=action,
            from_count=from_count,
            to_count=target_count if success else from_count,
            reason=reason,
            success=success,
        )

        self.scaling_history.append(history)

        # 保留最近100条记录
        if len(self.scaling_history) > 100:
            self.scaling_history = self.scaling_history[-100:]

        return success

    async def _auto_scale_loop(self) -> None:
        """自动扩缩容循环"""
        _logger.info("开始自动扩缩容循环")

        while self._scaling_active:
            try:
                # 获取当前负载指标
                metrics = await self.load_monitor.get_current_load()

                # 检查是否在冷却期
                if self._is_in_cooldown():
                    await asyncio.sleep(30)  # 冷却期间30秒检查一次
                    continue

                # 判断扩缩容动作
                action = ScalingAction.NO_CHANGE
                target_count = self.current_worker_count
                reason = ""

                if self._should_scale_up(metrics):
                    action = ScalingAction.SCALE_UP
                    target_count = min(
                        self.current_worker_count + self.config.scale_up_step,
                        self.config.max_workers,
                    )
                    reason = "负载过高需要扩容"

                elif self._should_scale_down(metrics):
                    action = ScalingAction.SCALE_DOWN
                    target_count = max(
                        self.current_worker_count - self.config.scale_down_step,
                        self.config.min_workers,
                    )
                    reason = "负载过低可以缩容"

                # 执行扩缩容
                if action != ScalingAction.NO_CHANGE:
                    await self._execute_scaling(action, target_count, reason)

                # 等待下一次检查
                await asyncio.sleep(60)  # 每分钟检查一次

            except Exception as e:
                _logger.error("自动扩缩容循环异常: %s", e)
                await asyncio.sleep(60)

        _logger.info("自动扩缩容循环已停止")


# 全局扩缩容实例
_scaler_instance: Optional[WorkerScaler] = None


def get_worker_scaler() -> WorkerScaler:
    """获取Worker扩缩容实例"""
    global _scaler_instance
    if _scaler_instance is None:
        _scaler_instance = WorkerScaler()
    return _scaler_instance
