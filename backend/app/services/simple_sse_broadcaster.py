"""
极简SSE广播器 - Linus重构版
消除队列映射、连接管理等复杂性，使用内存广播

完全类型安全，符合mypy --strict要求
"""

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional

logger: logging.Logger = logging.getLogger(__name__)


# 四步骤分析枚举 - 与前端保持一致
class AnalysisStep(str, Enum):
    DATA_COLLECTION = "data-collection"
    INTELLIGENT_ANALYSIS = "intelligent-analysis"
    INSIGHT_GENERATION = "insight-generation"
    REPORT_COMPILATION = "report-compilation"


# 实时统计数据类型
class AnalysisStats:
    """分析实时统计数据 - 完全类型安全"""

    def __init__(
        self,
        communities_found: int = 0,
        posts_analyzed: int = 0,
        insights_generated: int = 0,
        processing_time_seconds: int = 0,
    ) -> None:
        self.communities_found = communities_found
        self.posts_analyzed = posts_analyzed
        self.insights_generated = insights_generated
        self.processing_time_seconds = processing_time_seconds

    def to_dict(self) -> Dict[str, int]:
        """转换为字典格式用于JSON序列化"""
        return {
            "communities_found": self.communities_found,
            "posts_analyzed": self.posts_analyzed,
            "insights_generated": self.insights_generated,
            "processing_time_seconds": self.processing_time_seconds,
        }


class SSEConnection:
    """SSE连接的最小化表示 - 使用类而非dataclass避免哈希问题"""

    def __init__(self, queue: "asyncio.Queue[Mapping[str, Any]]", task_id: str) -> None:
        self.queue = queue
        self.task_id = task_id

    def __eq__(self, other: object) -> bool:
        """判断连接是否相等"""
        if not isinstance(other, SSEConnection):
            return False
        return self.queue == other.queue and self.task_id == other.task_id

    def __hash__(self) -> int:
        """使连接可哈希"""
        return hash((id(self.queue), self.task_id))


class SimpleSSEBroadcaster:
    """最简化的SSE广播器 - 零配置，直接工作"""

    def __init__(self) -> None:
        # 使用List而非Set，避免哈希问题
        self._connections: Dict[str, List[SSEConnection]] = {}

    def add_connection(
        self, task_id: str, queue: "asyncio.Queue[Mapping[str, Any]]"
    ) -> None:
        """添加连接 - 简单粗暴"""
        if task_id not in self._connections:
            self._connections[task_id] = []

        # 避免重复添加
        new_conn = SSEConnection(queue, task_id)
        if new_conn not in self._connections[task_id]:
            self._connections[task_id].append(new_conn)

    def remove_connection(
        self, task_id: str, queue: "asyncio.Queue[Mapping[str, Any]]"
    ) -> None:
        """移除连接"""
        if task_id not in self._connections:
            return

        # 过滤掉要移除的连接
        target_conn = SSEConnection(queue, task_id)
        self._connections[task_id] = [
            conn for conn in self._connections[task_id] if conn != target_conn
        ]

        # 如果没有连接了，删除task_id
        if not self._connections[task_id]:
            del self._connections[task_id]

    async def broadcast_task_update(
        self, task_id: str, status: str, progress: int, message: str
    ) -> None:
        """广播任务更新 - 核心功能"""
        if task_id not in self._connections:
            return

        # 构建消息
        update_data: dict[str, Any] = {
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 广播到所有连接
        dead_connections: List[SSEConnection] = []

        for conn in self._connections[task_id]:
            try:
                await conn.queue.put(update_data)
            except (asyncio.QueueFull, RuntimeError) as e:
                logger.warning(f"广播失败到连接 {conn.task_id}: {e}")
                dead_connections.append(conn)

        # 清理死连接
        for dead_conn in dead_connections:
            self._connections[task_id].remove(dead_conn)

        # 如果没有连接了，删除task_id
        if not self._connections[task_id]:
            del self._connections[task_id]

    async def broadcast_enhanced_progress(
        self,
        task_id: str,
        status: str,
        progress: int,
        message: str,
        current_step: Optional[AnalysisStep] = None,
        step_progress: Optional[int] = None,
        estimated_remaining_seconds: Optional[int] = None,
        stats: Optional[AnalysisStats] = None,
    ) -> None:
        """
        广播增强版任务进度 - 支持四步骤+实时统计
        基于v0界面需求设计，完全类型安全

        Args:
            task_id: 任务ID
            status: 任务状态 (pending/processing/completed/failed)
            progress: 整体进度 0-100
            message: 进度消息
            current_step: 当前分析步骤
            step_progress: 当前步骤进度 0-100
            estimated_remaining_seconds: 预估剩余秒数
            stats: 实时统计数据
        """
        if task_id not in self._connections:
            return

        # 构建增强版消息数据
        update_data: dict[str, Any] = {
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 添加v0界面扩展字段
        if current_step is not None:
            update_data["current_step"] = current_step.value

        if step_progress is not None:
            update_data["step_progress"] = step_progress

        if estimated_remaining_seconds is not None:
            update_data["estimated_remaining_seconds"] = estimated_remaining_seconds

        if stats is not None:
            update_data["stats"] = stats.to_dict()

        # 广播到所有连接
        dead_connections: List[SSEConnection] = []

        for conn in self._connections[task_id]:
            try:
                await conn.queue.put(update_data)
            except (asyncio.QueueFull, RuntimeError) as e:
                logger.warning(f"增强广播失败到连接 {conn.task_id}: {e}")
                dead_connections.append(conn)

        # 清理死连接
        for dead_conn in dead_connections:
            self._connections[task_id].remove(dead_conn)

        # 如果没有连接了，删除task_id
        if not self._connections[task_id]:
            del self._connections[task_id]

    def get_connection_count(self, task_id: Optional[str] = None) -> int:
        """获取连接数 - 调试用"""
        if task_id:
            return len(self._connections.get(task_id, []))
        return sum(len(conns) for conns in self._connections.values())

    def clear_all_connections(self) -> None:
        """清空所有连接 - 测试用"""
        self._connections.clear()


# 全局单例
_broadcaster: Optional[SimpleSSEBroadcaster] = None


def get_sse_broadcaster() -> SimpleSSEBroadcaster:
    """获取全局广播器实例"""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = SimpleSSEBroadcaster()
    return _broadcaster


def reset_sse_broadcaster() -> None:
    """重置广播器 - 测试用"""
    global _broadcaster
    _broadcaster = None


# 导出便利函数用于创建统计数据
def create_analysis_stats(
    communities: int = 0,
    posts: int = 0,
    insights: int = 0,
    processing_time: int = 0,
) -> AnalysisStats:
    """创建分析统计数据的便利函数 - 类型安全"""
    return AnalysisStats(communities, posts, insights, processing_time)


# 导出所有公共接口
__all__ = [
    "SimpleSSEBroadcaster",
    "AnalysisStep",
    "AnalysisStats",
    "get_sse_broadcaster",
    "create_analysis_stats",
    "reset_sse_broadcaster",
]
