"""
系统监控服务 - 实时监控Worker和队列状态

基于Linus原则：
1. 简单直接 - 批量查询替代复杂的订阅机制
2. 统一检查 - 单一监控循环处理所有指标
3. 配置驱动 - 可配置的检查间隔和阈值
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import psutil
from celery import Celery
from sqlalchemy.orm import Session

from app.core.config_manager import settings
from app.core.database import get_session_sync
from app.core.redis_client import RedisClient, get_redis_client
from app.core.task_status import UnifiedTaskStatus
from app.models.task import Task
from app.schemas.task_monitor import (
    Alert,
    QueueMetrics,
    SystemHealthResponse,
    WorkerStatus,
)

logger = logging.getLogger(__name__)


class SystemMonitor:
    """
    系统监控器 - 监控Worker健康和队列状态

    职责：
    1. Worker健康检查
    2. 队列积压监控
    3. 系统资源监控
    """

    def __init__(self) -> None:
        # 异步获取：延迟初始化
        self.redis_client: Optional[RedisClient] = None
        self.scan_interval = 30  # 默认30秒扫描一次
        self.health_check_timeout = 10  # 健康检查超时
        self.worker_timeout = 60  # Worker超时阈值
        self._running = False
        self._monitor_task: Optional[asyncio.Task[None]] = None

    async def _client(self) -> RedisClient:
        """获取异步 Redis 客户端（延迟初始化）。"""
        if self.redis_client is None:
            self.redis_client = await get_redis_client()
        return self.redis_client

    # ==================== Worker监控 ====================

    async def check_worker_health(self, worker_id: str) -> WorkerStatus:
        """检查单个Worker健康状态"""
        heartbeat_key = f"worker:{worker_id}:heartbeat"
        stats_key = f"worker:{worker_id}:stats"

        # 获取心跳时间
        client = await self._client()
        heartbeat_data: Any = await client.get(heartbeat_key)
        if not heartbeat_data:
            # Worker从未注册
            return WorkerStatus(
                worker_id=worker_id,
                hostname="unknown",
                is_alive=False,
                last_heartbeat=datetime.now(timezone.utc),
                started_at=datetime.now(timezone.utc),
            )

        try:
            heartbeat_info = (
                json.loads(heartbeat_data)
                if isinstance(heartbeat_data, str)
                else heartbeat_data
            )
            last_heartbeat = datetime.fromisoformat(heartbeat_info["timestamp"])

            # 检查是否超时（连续3次失败才判定宕机）
            time_since_heartbeat = (
                datetime.now(timezone.utc) - last_heartbeat
            ).total_seconds()
            is_alive = time_since_heartbeat < self.worker_timeout * 3

            # 获取统计信息
            stats_raw = await client.get(stats_key)
            if stats_raw:
                stats = (
                    json.loads(stats_raw) if isinstance(stats_raw, str) else stats_raw
                )
                active_tasks = stats.get("active_tasks", 0)
                completed_tasks = stats.get("completed_tasks", 0)
                failed_tasks = stats.get("failed_tasks", 0)

                # 获取系统资源使用（如果Worker在本机）
                cpu_percent, memory_percent = self._get_worker_resources(worker_id)
            else:
                active_tasks = completed_tasks = failed_tasks = 0
                cpu_percent = memory_percent = 0

            return WorkerStatus(
                worker_id=worker_id,
                hostname=heartbeat_info.get("hostname", "unknown"),
                is_alive=is_alive,
                last_heartbeat=last_heartbeat,
                active_tasks=active_tasks,
                completed_tasks=completed_tasks,
                failed_tasks=failed_tasks,
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                started_at=datetime.fromisoformat(
                    heartbeat_info.get(
                        "started_at", datetime.now(timezone.utc).isoformat()
                    )
                ),
            )

        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.error(f"检查Worker健康失败: {worker_id}, 错误: {e}")
            return WorkerStatus(
                worker_id=worker_id,
                hostname="unknown",
                is_alive=False,
                last_heartbeat=datetime.now(timezone.utc),
                started_at=datetime.now(timezone.utc),
            )

    def _get_worker_resources(self, worker_id: str) -> Tuple[float, float]:
        """获取Worker资源使用情况"""
        try:
            # 尝试获取进程信息（仅本机Worker）
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                if worker_id in str(proc.info.get("cmdline", [])):
                    cpu_percent = proc.cpu_percent(interval=0.1)
                    memory_info = proc.memory_info()
                    memory_percent = (
                        memory_info.rss / psutil.virtual_memory().total
                    ) * 100
                    return cpu_percent, memory_percent
        except (psutil.Error, OSError, RuntimeError, ValueError) as e:
            logger.debug(f"无法获取Worker资源: {worker_id}, {e}")

        return 0.0, 0.0

    async def get_all_workers(self) -> List[WorkerStatus]:
        """获取所有Worker状态"""
        client = await self._client()
        pattern = "worker:*:heartbeat"
        workers: List[WorkerStatus] = []

        keys = await client.keys(pattern)
        for key in keys:
            worker_id = key.split(":")[1]
            worker_status = await self.check_worker_health(worker_id)
            workers.append(worker_status)

        return workers

    # ==================== 队列监控 ====================

    def get_queue_metrics(self, queue_name: str = "default") -> QueueMetrics:
        """获取队列指标"""
        db: Session = get_session_sync()
        try:
            now = datetime.now(timezone.utc)

            # 统计各状态任务数
            # Task 模型不含 queue_name 字段，统一使用默认队列过滤移除
            pending_count = (
                db.query(Task)
                .filter(
                    Task.status == UnifiedTaskStatus.PENDING.value,
                )
                .count()
            )

            processing_count = (
                db.query(Task)
                .filter(
                    Task.status == UnifiedTaskStatus.PROCESSING.value,
                )
                .count()
            )

            completed_count = (
                db.query(Task)
                .filter(
                    Task.status == UnifiedTaskStatus.COMPLETED.value,
                    Task.completed_at >= now - timedelta(hours=1),  # 最近1小时
                )
                .count()
            )

            failed_count = (
                db.query(Task)
                .filter(
                    Task.status == UnifiedTaskStatus.FAILED.value,
                    Task.completed_at >= now - timedelta(hours=1),  # 最近1小时
                )
                .count()
            )

            # 计算平均处理时间（最近100个完成的任务）
            recent_tasks = (
                db.query(Task)
                .filter(
                    Task.status == UnifiedTaskStatus.COMPLETED.value,
                    Task.started_at.isnot(None),
                    Task.completed_at.isnot(None),
                )
                .order_by(Task.completed_at.desc())
                .limit(100)
                .all()
            )

            if recent_tasks:
                processing_times = []
                for task in recent_tasks:
                    if task.started_at and task.completed_at:
                        processing_times.append(
                            (task.completed_at - task.started_at).total_seconds()
                        )
                avg_processing_time = sum(processing_times) / len(processing_times)
                max_processing_time = max(processing_times)
            else:
                avg_processing_time = 0
                max_processing_time = 0

            # 获取最老的待处理任务
            oldest_pending = (
                db.query(Task)
                .filter(Task.status == UnifiedTaskStatus.PENDING.value)
                .order_by(Task.created_at.asc())
                .first()
            )

            if oldest_pending:
                oldest_task_age = (now - oldest_pending.created_at).total_seconds()
            else:
                oldest_task_age = 0

            return QueueMetrics(
                queue_name=queue_name,
                pending_count=pending_count,
                processing_count=processing_count,
                completed_count=completed_count,
                failed_count=failed_count,
                avg_processing_time=avg_processing_time,
                max_processing_time=max_processing_time,
                oldest_task_age=oldest_task_age,
                measured_at=now,
            )

        finally:
            db.close()

    def get_all_queues(self) -> List[QueueMetrics]:
        """获取所有队列的指标"""
        db: Session = get_session_sync()
        try:
            # 获取所有不同的队列名
            # 任务模型无 queue_name 字段，统一仅返回默认队列指标
            queue_names = [("default",)]

            metrics = []
            for (queue_name,) in queue_names:
                if queue_name:
                    queue_metrics = self.get_queue_metrics(queue_name)
                    metrics.append(queue_metrics)

            # 如果没有队列，至少返回默认队列
            if not metrics:
                metrics.append(self.get_queue_metrics("default"))

            return metrics

        finally:
            db.close()

    # ==================== 系统健康状态 ====================

    async def get_system_health(self) -> SystemHealthResponse:
        """获取系统整体健康状态"""
        workers = await self.get_all_workers()
        queues = self.get_all_queues()

        # 统计健康的Worker数
        healthy_workers = sum(1 for w in workers if w.is_healthy)

        # 判断系统状态
        if not workers or healthy_workers == 0:
            system_status = "critical"
        elif healthy_workers < len(workers) / 2:
            system_status = "degraded"
        else:
            system_status = "healthy"

        # 获取活跃告警（这里简化处理，实际应该从AlertProcessor获取）
        active_alerts: List[Alert] = []

        return SystemHealthResponse(
            workers=workers,
            queues=queues,
            active_alerts=active_alerts,
            total_workers=len(workers),
            healthy_workers=healthy_workers,
            total_queues=len(queues),
            system_status=system_status,
        )

    # ==================== 监控循环 ====================

    async def start_monitoring(self, interval: Optional[int] = None) -> None:
        """启动监控循环"""
        if self._running:
            logger.warning("监控已在运行中")
            return

        self._running = True
        self.scan_interval = interval or self.scan_interval

        logger.info(f"启动系统监控，扫描间隔: {self.scan_interval}秒")

        while self._running:
            try:
                # 执行监控检查
                await self._monitor_cycle()

                # 等待下一个周期
                await asyncio.sleep(self.scan_interval)

            except asyncio.CancelledError:
                raise
            except (OSError, RuntimeError, ValueError) as e:
                logger.error(f"监控循环错误: {e}")
                await asyncio.sleep(5)  # 错误后短暂等待

    async def _monitor_cycle(self) -> None:
        """单个监控周期"""
        # 检查Worker健康
        workers = await self.get_all_workers()
        for worker in workers:
            if not worker.is_healthy:
                logger.warning(f"Worker不健康: {worker.worker_id}")
                # 这里可以触发告警

        # 检查队列积压
        queues = self.get_all_queues()
        for queue in queues:
            if queue.pending_count > 100:  # 可配置的阈值
                logger.warning(f"队列积压: {queue.queue_name}, 待处理: {queue.pending_count}")
                # 这里可以触发告警

        # 保存监控快照到Redis
        await self._save_monitoring_snapshot(workers, queues)

    async def _save_monitoring_snapshot(
        self, workers: List[WorkerStatus], queues: List[QueueMetrics]
    ) -> None:
        """保存监控快照"""
        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "workers": {
                "total": len(workers),
                "healthy": sum(1 for w in workers if w.is_healthy),
                "ids": [w.worker_id for w in workers],
            },
            "queues": {
                "total": len(queues),
                "pending_total": sum(q.pending_count for q in queues),
                "processing_total": sum(q.processing_count for q in queues),
            },
        }

        client = await self._client()
        # 保存到Redis，保留1小时
        await client.set("monitoring:snapshot:latest", json.dumps(snapshot), ttl=3600)

        # 保存到时间序列（用于历史查询）
        ts_key = (
            f"monitoring:snapshot:{datetime.now(timezone.utc).strftime('%Y%m%d:%H')}"
        )
        await client.lpush(ts_key, json.dumps(snapshot))
        await client.expire(ts_key, 86400)  # 保留24小时

    def stop_monitoring(self) -> None:
        """停止监控循环"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
        logger.info("系统监控已停止")


# 单例实例
_monitor_instance: Optional[SystemMonitor] = None


def get_system_monitor() -> SystemMonitor:
    """获取系统监控器单例"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = SystemMonitor()
    return _monitor_instance
