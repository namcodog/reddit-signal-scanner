"""
负载监控组件

基于Celery事件系统实现Worker负载监控，支持：
- 队列长度监控
- Worker心跳检测
- 系统资源监控
- 任务处理统计
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

import psutil
from celery import Celery
from celery.events import Event

from .celery_app import get_active_tasks, get_celery_app, get_queue_lengths
from .types import ActiveTasksOverview

_logger = logging.getLogger(__name__)


class LoadLevel(Enum):
    """负载级别枚举"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class WorkerMetrics:
    """Worker度量指标"""

    hostname: str
    active_tasks: int
    processed_tasks: int
    last_heartbeat: Optional[datetime]
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    is_online: bool = True


@dataclass
class QueueMetrics:
    """队列度量指标"""

    name: str
    length: int
    consumers: int = 0
    messages_per_minute: float = 0.0


@dataclass
class LoadMetrics:
    """系统负载度量"""

    timestamp: datetime = field(default_factory=datetime.now)
    total_workers: int = 0
    online_workers: int = 0
    total_active_tasks: int = 0
    queue_metrics: Dict[str, QueueMetrics] = field(default_factory=dict)
    worker_metrics: Dict[str, WorkerMetrics] = field(default_factory=dict)
    system_cpu: float = 0.0
    system_memory: float = 0.0
    load_level: LoadLevel = LoadLevel.NORMAL


@dataclass
class LoadThresholds:
    """负载阈值配置"""

    queue_high_threshold: int = 50
    queue_critical_threshold: int = 100
    cpu_high_threshold: float = 80.0
    cpu_critical_threshold: float = 90.0
    memory_high_threshold: float = 85.0
    memory_critical_threshold: float = 95.0
    worker_timeout_seconds: int = 120


class LoadMonitor:
    """负载监控器"""

    def __init__(
        self,
        celery_app: Optional[Celery] = None,
        thresholds: Optional[LoadThresholds] = None,
    ) -> None:
        """初始化负载监控器"""
        self.celery = celery_app or get_celery_app()
        self.thresholds = thresholds or LoadThresholds()
        self.workers: Dict[str, WorkerMetrics] = {}
        self.last_metrics: Optional[LoadMetrics] = None
        self._monitoring = False
        self._event_receivers: List[asyncio.Task[None]] = []

    async def start_monitoring(self) -> None:
        """启动负载监控"""
        if self._monitoring:
            _logger.warning("负载监控已在运行")
            return

        self._monitoring = True
        _logger.info("启动负载监控器")

        # 启用Celery事件
        try:
            self.celery.control.enable_events()
        except Exception as e:
            _logger.error("启用Celery事件失败: %s", e)

        # 启动事件监听
        event_task = asyncio.create_task(self._monitor_events())
        self._event_receivers.append(event_task)

    async def stop_monitoring(self) -> None:
        """停止负载监控"""
        if not self._monitoring:
            return

        self._monitoring = False
        _logger.info("停止负载监控器")

        # 取消所有事件接收器
        for task in self._event_receivers:
            task.cancel()

        # 等待任务完成
        if self._event_receivers:
            await asyncio.gather(*self._event_receivers, return_exceptions=True)
        self._event_receivers.clear()

    async def get_current_load(self) -> LoadMetrics:
        """获取当前负载指标"""
        try:
            # 获取队列长度
            queue_lengths = await self._get_queue_lengths()
            queue_metrics = {
                name: QueueMetrics(name=name, length=length)
                for name, length in queue_lengths.items()
            }

            # 获取活跃任务信息
            active_tasks = await self._get_active_tasks()
            total_active = active_tasks.get("total_active", 0)

            # 获取系统资源信息
            system_cpu = psutil.cpu_percent(interval=1)
            system_memory = psutil.virtual_memory().percent

            # 更新Worker信息
            await self._update_worker_status()

            # 计算负载级别
            load_level = self._calculate_load_level(
                queue_metrics, system_cpu, system_memory
            )

            metrics = LoadMetrics(
                total_workers=len(self.workers),
                online_workers=sum(1 for w in self.workers.values() if w.is_online),
                total_active_tasks=total_active,
                queue_metrics=queue_metrics,
                worker_metrics=self.workers.copy(),
                system_cpu=system_cpu,
                system_memory=system_memory,
                load_level=load_level,
            )

            self.last_metrics = metrics
            return metrics

        except Exception as e:
            _logger.error("获取负载指标失败: %s", e)
            return self.last_metrics or LoadMetrics()

    def is_scale_up_needed(self) -> bool:
        """判断是否需要扩容"""
        if not self.last_metrics:
            return False

        # 检查负载级别
        if self.last_metrics.load_level in (
            LoadLevel.HIGH,
            LoadLevel.CRITICAL,
        ):
            return True

        # 检查队列长度
        for queue_name, queue in self.last_metrics.queue_metrics.items():
            if queue.length > self.thresholds.queue_high_threshold:
                _logger.info(
                    "队列 %s 长度 %d 超过阈值 %d，建议扩容",
                    queue_name,
                    queue.length,
                    self.thresholds.queue_high_threshold,
                )
                return True

        return False

    def is_scale_down_needed(self) -> bool:
        """判断是否需要缩容"""
        if not self.last_metrics:
            return False

        # 检查负载级别
        if self.last_metrics.load_level == LoadLevel.LOW:
            # 检查是否所有队列都是空的或很少任务
            all_queues_low = all(
                queue.length < 5 for queue in self.last_metrics.queue_metrics.values()
            )

            if all_queues_low and self.last_metrics.total_active_tasks < 2:
                _logger.info("系统负载较低，建议缩容")
                return True

        return False

    async def _get_queue_lengths(self) -> Dict[str, int]:
        """异步获取队列长度"""
        try:
            return get_queue_lengths()
        except Exception as e:
            _logger.error("获取队列长度失败: %s", e)
            return {}

    async def _get_active_tasks(self) -> ActiveTasksOverview:
        """异步获取活跃任务"""
        try:
            return get_active_tasks()
        except Exception as e:
            _logger.error("获取活跃任务失败: %s", e)
            return {
                "active": {},
                "scheduled": {},
                "reserved": {},
                "total_active": 0,
                "total_scheduled": 0,
                "total_reserved": 0,
            }

    async def _update_worker_status(self) -> None:
        """更新Worker状态"""
        try:
            inspect = self.celery.control.inspect()
            stats = inspect.stats()

            if not stats:
                _logger.warning("无法获取Worker统计信息")
                return

            current_time = datetime.now()

            # 标记所有Worker为离线
            for worker_name in self.workers:
                self.workers[worker_name].is_online = False

            # 更新在线Worker信息
            for hostname, stat in stats.items():
                if hostname not in self.workers:
                    self.workers[hostname] = WorkerMetrics(
                        hostname=hostname,
                        active_tasks=0,
                        processed_tasks=0,
                        last_heartbeat=current_time,
                    )

                worker = self.workers[hostname]
                worker.is_online = True
                worker.last_heartbeat = current_time
                worker.processed_tasks = stat.get("total", {}).get("tasks.add", 0)

        except Exception as e:
            _logger.error("更新Worker状态失败: %s", e)

    def _calculate_load_level(
        self,
        queue_metrics: Dict[str, QueueMetrics],
        cpu_usage: float,
        memory_usage: float,
    ) -> LoadLevel:
        """计算负载级别"""
        # 检查临界条件
        if (
            cpu_usage > self.thresholds.cpu_critical_threshold
            or memory_usage > self.thresholds.memory_critical_threshold
        ):
            return LoadLevel.CRITICAL

        for queue in queue_metrics.values():
            if queue.length > self.thresholds.queue_critical_threshold:
                return LoadLevel.CRITICAL

        # 检查高负载条件
        if (
            cpu_usage > self.thresholds.cpu_high_threshold
            or memory_usage > self.thresholds.memory_high_threshold
        ):
            return LoadLevel.HIGH

        for queue in queue_metrics.values():
            if queue.length > self.thresholds.queue_high_threshold:
                return LoadLevel.HIGH

        # 检查低负载条件
        all_queues_empty = all(queue.length < 5 for queue in queue_metrics.values())

        if all_queues_empty and cpu_usage < 30.0 and memory_usage < 50.0:
            return LoadLevel.LOW

        return LoadLevel.NORMAL

    async def _monitor_events(self) -> None:
        """监控Celery事件"""
        try:
            with self.celery.connection() as connection:
                recv = self.celery.events.Receiver(
                    connection,
                    handlers={
                        "worker-heartbeat": self._handle_worker_heartbeat,
                        "worker-online": self._handle_worker_online,
                        "worker-offline": self._handle_worker_offline,
                        "task-sent": self._handle_task_sent,
                        "task-received": self._handle_task_received,
                        "task-started": self._handle_task_started,
                        "task-succeeded": self._handle_task_succeeded,
                        "task-failed": self._handle_task_failed,
                    },
                )

                _logger.info("开始监听Celery事件")
                recv.capture(limit=None, timeout=None, wakeup=True)

        except Exception as e:
            if self._monitoring:
                _logger.error("事件监听失败: %s", e)

    def _handle_worker_heartbeat(self, event: Event) -> None:
        """处理Worker心跳事件"""
        hostname = event.get("hostname")
        if not hostname:
            return

        if hostname not in self.workers:
            self.workers[hostname] = WorkerMetrics(
                hostname=hostname,
                active_tasks=0,
                processed_tasks=0,
                last_heartbeat=None,
            )

        worker = self.workers[hostname]
        worker.last_heartbeat = datetime.fromtimestamp(event["timestamp"])
        worker.active_tasks = event.get("active", 0)
        worker.processed_tasks = event.get("processed", 0)
        worker.is_online = True

    def _handle_worker_online(self, event: Event) -> None:
        """处理Worker上线事件"""
        hostname = event.get("hostname")
        if not hostname:
            return

        if hostname not in self.workers:
            self.workers[hostname] = WorkerMetrics(
                hostname=hostname,
                active_tasks=0,
                processed_tasks=0,
                last_heartbeat=datetime.fromtimestamp(event["timestamp"]),
            )

        self.workers[hostname].is_online = True
        _logger.info("Worker上线: %s", hostname)

    def _handle_worker_offline(self, event: Event) -> None:
        """处理Worker下线事件"""
        hostname = event.get("hostname")
        if hostname and hostname in self.workers:
            self.workers[hostname].is_online = False
            _logger.info("Worker下线: %s", hostname)

    def _handle_task_sent(self, event: Event) -> None:
        """处理任务发送事件"""
        pass  # 暂不处理

    def _handle_task_received(self, event: Event) -> None:
        """处理任务接收事件"""
        pass  # 暂不处理

    def _handle_task_started(self, event: Event) -> None:
        """处理任务开始事件"""
        hostname = event.get("hostname")
        if hostname and hostname in self.workers:
            self.workers[hostname].active_tasks += 1

    def _handle_task_succeeded(self, event: Event) -> None:
        """处理任务成功事件"""
        hostname = event.get("hostname")
        if hostname and hostname in self.workers:
            worker = self.workers[hostname]
            worker.active_tasks = max(0, worker.active_tasks - 1)
            worker.processed_tasks += 1

    def _handle_task_failed(self, event: Event) -> None:
        """处理任务失败事件"""
        hostname = event.get("hostname")
        if hostname and hostname in self.workers:
            worker = self.workers[hostname]
            worker.active_tasks = max(0, worker.active_tasks - 1)


# 全局监控器实例
_monitor_instance: Optional[LoadMonitor] = None


def get_load_monitor() -> LoadMonitor:
    """获取负载监控器实例"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = LoadMonitor()
    return _monitor_instance
