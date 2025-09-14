"""
负载均衡器

基于Celery任务分发实现负载均衡策略，支持：
- 多种负载均衡算法
- Worker健康状态监控
- 任务重新分发
- 动态权重调整
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from celery import Celery

from .celery_app import get_celery_app
from .load_monitor import LoadMonitor, WorkerMetrics, get_load_monitor
from .types import JsonValue

_logger = logging.getLogger(__name__)


class LoadBalancingStrategy(Enum):
    """负载均衡策略枚举"""

    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    RESOURCE_BASED = "resource_based"


@dataclass
class WorkerWeight:
    """Worker权重配置"""

    hostname: str
    weight: int = 100  # 默认权重100
    current_load: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
    is_healthy: bool = True


@dataclass
class TaskDistribution:
    """任务分发结果"""

    worker_hostname: str
    task_count: int
    estimated_completion_time: float
    reason: str


class LoadBalancingAlgorithm(ABC):
    """负载均衡算法抽象基类"""

    @abstractmethod
    def select_worker(
        self,
        available_workers: List[WorkerMetrics],
        worker_weights: Dict[str, WorkerWeight],
    ) -> Optional[str]:
        """选择最优Worker"""
        pass


class RoundRobinAlgorithm(LoadBalancingAlgorithm):
    """轮询算法"""

    def __init__(self) -> None:
        self.current_index = 0

    def select_worker(
        self,
        available_workers: List[WorkerMetrics],
        worker_weights: Dict[str, WorkerWeight],
    ) -> Optional[str]:
        """轮询选择Worker"""
        if not available_workers:
            return None

        # 过滤健康的Worker
        healthy_workers = [
            w
            for w in available_workers
            if w.is_online
            and worker_weights.get(w.hostname, WorkerWeight(w.hostname)).is_healthy
        ]

        if not healthy_workers:
            return None

        selected_worker = healthy_workers[self.current_index % len(healthy_workers)]
        self.current_index = (self.current_index + 1) % len(healthy_workers)

        return selected_worker.hostname


class LeastConnectionsAlgorithm(LoadBalancingAlgorithm):
    """最少连接算法"""

    def select_worker(
        self,
        available_workers: List[WorkerMetrics],
        worker_weights: Dict[str, WorkerWeight],
    ) -> Optional[str]:
        """选择活跃任务最少的Worker"""
        if not available_workers:
            return None

        # 过滤健康的在线Worker
        healthy_workers = [
            w
            for w in available_workers
            if w.is_online
            and worker_weights.get(w.hostname, WorkerWeight(w.hostname)).is_healthy
        ]

        if not healthy_workers:
            return None

        # 选择活跃任务数最少的Worker
        min_tasks_worker = min(healthy_workers, key=lambda w: w.active_tasks)
        return min_tasks_worker.hostname


class WeightedRoundRobinAlgorithm(LoadBalancingAlgorithm):
    """加权轮询算法"""

    def __init__(self) -> None:
        self.current_weights: Dict[str, int] = {}

    def select_worker(
        self,
        available_workers: List[WorkerMetrics],
        worker_weights: Dict[str, WorkerWeight],
    ) -> Optional[str]:
        """基于权重轮询选择Worker"""
        if not available_workers:
            return None

        # 过滤健康的Worker
        healthy_workers = [
            w
            for w in available_workers
            if w.is_online
            and worker_weights.get(w.hostname, WorkerWeight(w.hostname)).is_healthy
        ]

        if not healthy_workers:
            return None

        # 初始化权重
        for worker in healthy_workers:
            if worker.hostname not in self.current_weights:
                weight = worker_weights.get(
                    worker.hostname, WorkerWeight(worker.hostname)
                ).weight
                self.current_weights[worker.hostname] = weight

        # 选择当前权重最高的Worker
        selected_hostname = max(
            [w.hostname for w in healthy_workers],
            key=lambda hostname: self.current_weights.get(hostname, 0),
        )

        # 减少选中Worker的权重
        if selected_hostname in self.current_weights:
            self.current_weights[selected_hostname] -= 1

        # 如果所有权重都为0，重置权重
        if all(w <= 0 for w in self.current_weights.values()):
            for worker in healthy_workers:
                weight = worker_weights.get(
                    worker.hostname, WorkerWeight(worker.hostname)
                ).weight
                self.current_weights[worker.hostname] = weight

        return selected_hostname


class ResourceBasedAlgorithm(LoadBalancingAlgorithm):
    """基于资源的算法"""

    def select_worker(
        self,
        available_workers: List[WorkerMetrics],
        worker_weights: Dict[str, WorkerWeight],
    ) -> Optional[str]:
        """基于CPU和内存使用率选择Worker"""
        if not available_workers:
            return None

        # 过滤健康的Worker
        healthy_workers = [
            w
            for w in available_workers
            if w.is_online
            and worker_weights.get(w.hostname, WorkerWeight(w.hostname)).is_healthy
        ]

        if not healthy_workers:
            return None

        # 计算每个Worker的资源得分（越低越好）
        def calculate_resource_score(worker: WorkerMetrics) -> float:
            # 权重：CPU占50%，内存占30%，活跃任务数占20%
            cpu_score = worker.cpu_usage / 100.0  # 标准化到0-1
            memory_score = worker.memory_usage / 100.0  # 标准化到0-1
            task_score = min(worker.active_tasks / 10.0, 1.0)  # 最多10个任务

            return 0.5 * cpu_score + 0.3 * memory_score + 0.2 * task_score

        # 选择资源得分最低的Worker
        best_worker = min(healthy_workers, key=calculate_resource_score)
        return best_worker.hostname


class LoadBalancer:
    """负载均衡器"""

    def __init__(
        self,
        celery_app: Optional[Celery] = None,
        load_monitor: Optional[LoadMonitor] = None,
        strategy: LoadBalancingStrategy = (LoadBalancingStrategy.LEAST_CONNECTIONS),
    ) -> None:
        """初始化负载均衡器"""
        self.celery = celery_app or get_celery_app()
        self.load_monitor = load_monitor or get_load_monitor()
        self.strategy = strategy
        self.worker_weights: Dict[str, WorkerWeight] = {}
        self.algorithms = self._initialize_algorithms()
        self.task_history: List[Dict[str, Any]] = []

    def _initialize_algorithms(
        self,
    ) -> Dict[LoadBalancingStrategy, LoadBalancingAlgorithm]:
        """初始化算法实例"""
        return {
            LoadBalancingStrategy.ROUND_ROBIN: RoundRobinAlgorithm(),
            LoadBalancingStrategy.LEAST_CONNECTIONS: (LeastConnectionsAlgorithm()),
            LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN: (WeightedRoundRobinAlgorithm()),
            LoadBalancingStrategy.RESOURCE_BASED: ResourceBasedAlgorithm(),
        }

    def set_strategy(self, strategy: LoadBalancingStrategy) -> None:
        """设置负载均衡策略"""
        self.strategy = strategy
        _logger.info("负载均衡策略已切换到: %s", strategy.value)

    def set_worker_weight(self, hostname: str, weight: int) -> None:
        """设置Worker权重"""
        if hostname not in self.worker_weights:
            self.worker_weights[hostname] = WorkerWeight(hostname=hostname)

        self.worker_weights[hostname].weight = weight
        self.worker_weights[hostname].last_updated = datetime.now()

        _logger.info("设置Worker权重: %s = %d", hostname, weight)

    async def select_worker(self) -> Optional[str]:
        """选择最佳Worker"""
        try:
            # 获取当前负载指标
            current_load = await self.load_monitor.get_current_load()
            available_workers = list(current_load.worker_metrics.values())

            if not available_workers:
                _logger.warning("没有可用的Worker")
                return None

            # 更新Worker权重信息
            await self._update_worker_weights(available_workers)

            # 使用当前策略选择Worker
            algorithm = self.algorithms.get(self.strategy)
            if not algorithm:
                _logger.error("未找到负载均衡算法: %s", self.strategy)
                return None

            selected_hostname = algorithm.select_worker(
                available_workers, self.worker_weights
            )

            if selected_hostname:
                _logger.debug(
                    "选择Worker: %s (策略: %s)",
                    selected_hostname,
                    self.strategy.value,
                )

            return selected_hostname

        except Exception as e:
            _logger.error("选择Worker失败: %s", e)
            return None

    async def distribute_tasks(self, task_count: int) -> List[TaskDistribution]:
        """分发多个任务到不同Worker"""
        try:
            current_load = await self.load_monitor.get_current_load()
            available_workers = [
                w for w in current_load.worker_metrics.values() if w.is_online
            ]

            if not available_workers:
                return []

            distributions: List[TaskDistribution] = []

            # 根据策略分发任务
            if self.strategy == LoadBalancingStrategy.RESOURCE_BASED:
                distributions = await self._distribute_by_resources(
                    task_count, available_workers
                )
            else:
                distributions = await self._distribute_evenly(
                    task_count, available_workers
                )

            return distributions

        except Exception as e:
            _logger.error("分发任务失败: %s", e)
            return []

    async def rebalance_load(self) -> bool:
        """重新平衡负载"""
        try:
            current_load = await self.load_monitor.get_current_load()

            # 识别过载的Worker
            overloaded_workers = await self._identify_overloaded_workers(
                current_load.worker_metrics
            )

            # 识别空闲的Worker
            idle_workers = await self._identify_idle_workers(
                current_load.worker_metrics
            )

            if not overloaded_workers or not idle_workers:
                _logger.debug("无需重新平衡负载")
                return True

            # 执行负载重平衡
            success = await self._execute_rebalancing(overloaded_workers, idle_workers)

            if success:
                _logger.info("负载重平衡完成")
            else:
                _logger.warning("负载重平衡失败")

            return success

        except Exception as e:
            _logger.error("重新平衡负载失败: %s", e)
            return False

    async def get_balancer_status(self) -> Dict[str, JsonValue]:
        """获取负载均衡器状态"""
        try:
            current_load = await self.load_monitor.get_current_load()

            return {
                "strategy": self.strategy.value,
                "total_workers": len(self.worker_weights),
                "healthy_workers": sum(
                    1 for w in self.worker_weights.values() if w.is_healthy
                ),
                "worker_weights": {
                    hostname: {
                        "weight": weight.weight,
                        "current_load": weight.current_load,
                        "is_healthy": weight.is_healthy,
                        "last_updated": weight.last_updated.isoformat(),
                    }
                    for hostname, weight in self.worker_weights.items()
                },
                "load_distribution": {
                    hostname: metrics.active_tasks
                    for hostname, metrics in current_load.worker_metrics.items()
                },
                "recent_selections": self.task_history[-10:],  # 最近10次选择
            }

        except Exception as e:
            _logger.error("获取负载均衡器状态失败: %s", e)
            return {"error": str(e)}

    async def _update_worker_weights(self, workers: List[WorkerMetrics]) -> None:
        """更新Worker权重信息"""
        for worker in workers:
            if worker.hostname not in self.worker_weights:
                self.worker_weights[worker.hostname] = WorkerWeight(
                    hostname=worker.hostname
                )

            weight_info = self.worker_weights[worker.hostname]

            # 更新负载信息
            weight_info.current_load = worker.active_tasks
            weight_info.is_healthy = worker.is_online
            weight_info.last_updated = datetime.now()

            # 基于负载动态调整权重
            if worker.active_tasks > 10:
                weight_info.weight = max(10, weight_info.weight - 10)
            elif worker.active_tasks < 2:
                weight_info.weight = min(200, weight_info.weight + 5)

    async def _distribute_by_resources(
        self, task_count: int, workers: List[WorkerMetrics]
    ) -> List[TaskDistribution]:
        """基于资源情况分发任务"""
        distributions: List[TaskDistribution] = []

        # 计算每个Worker的容量
        total_capacity = sum(
            max(1, 10 - w.active_tasks) for w in workers if w.is_online
        )

        if total_capacity == 0:
            return distributions

        # 按容量比例分发任务
        remaining_tasks = task_count

        for worker in workers:
            if not worker.is_online or remaining_tasks <= 0:
                continue

            capacity = max(1, 10 - worker.active_tasks)
            task_share = int((capacity / total_capacity) * task_count)
            task_share = min(task_share, remaining_tasks)

            if task_share > 0:
                distributions.append(
                    TaskDistribution(
                        worker_hostname=worker.hostname,
                        task_count=task_share,
                        estimated_completion_time=task_share * 2.0,  # 估算
                        reason="基于资源容量分配",
                    )
                )
                remaining_tasks -= task_share

        return distributions

    async def _distribute_evenly(
        self, task_count: int, workers: List[WorkerMetrics]
    ) -> List[TaskDistribution]:
        """平均分发任务"""
        distributions: List[TaskDistribution] = []
        online_workers = [w for w in workers if w.is_online]

        if not online_workers:
            return distributions

        tasks_per_worker = task_count // len(online_workers)
        remaining_tasks = task_count % len(online_workers)

        for i, worker in enumerate(online_workers):
            task_share = tasks_per_worker
            if i < remaining_tasks:
                task_share += 1

            if task_share > 0:
                distributions.append(
                    TaskDistribution(
                        worker_hostname=worker.hostname,
                        task_count=task_share,
                        estimated_completion_time=task_share * 2.0,
                        reason="平均分配",
                    )
                )

        return distributions

    async def _identify_overloaded_workers(
        self, worker_metrics: Dict[str, WorkerMetrics]
    ) -> List[str]:
        """识别过载的Worker"""
        overloaded = []

        for hostname, metrics in worker_metrics.items():
            if (
                metrics.is_online
                and metrics.active_tasks > 15  # 活跃任务超过15个
                and metrics.cpu_usage > 90.0
            ):  # CPU使用率超过90%
                overloaded.append(hostname)

        return overloaded

    async def _identify_idle_workers(
        self, worker_metrics: Dict[str, WorkerMetrics]
    ) -> List[str]:
        """识别空闲的Worker"""
        idle = []

        for hostname, metrics in worker_metrics.items():
            if (
                metrics.is_online
                and metrics.active_tasks < 3  # 活跃任务少于3个
                and metrics.cpu_usage < 50.0
            ):  # CPU使用率低于50%
                idle.append(hostname)

        return idle

    async def _execute_rebalancing(
        self, overloaded_workers: List[str], idle_workers: List[str]
    ) -> bool:
        """执行负载重平衡"""
        try:
            # 这里可以实现任务迁移逻辑
            # 由于Celery的限制，实际的任务迁移比较复杂
            # 主要通过调整权重来影响后续任务分配

            for hostname in overloaded_workers:
                if hostname in self.worker_weights:
                    self.worker_weights[hostname].weight = max(
                        10, self.worker_weights[hostname].weight - 20
                    )

            for hostname in idle_workers:
                if hostname in self.worker_weights:
                    self.worker_weights[hostname].weight = min(
                        200, self.worker_weights[hostname].weight + 20
                    )

            _logger.info(
                "调整Worker权重: 过载=%s, 空闲=%s",
                overloaded_workers,
                idle_workers,
            )

            return True

        except Exception as e:
            _logger.error("执行重平衡失败: %s", e)
            return False


# 全局负载均衡器实例
_balancer_instance: Optional[LoadBalancer] = None


def get_load_balancer() -> LoadBalancer:
    """获取负载均衡器实例"""
    global _balancer_instance
    if _balancer_instance is None:
        _balancer_instance = LoadBalancer()
    return _balancer_instance
