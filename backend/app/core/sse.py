"""
Reddit Signal Scanner - 极简SSE推送系统 (Linus重构版)

基于架构预审的极简设计：
- 统一SSE系统，删除架构分裂
- 2种核心数据结构，消除复杂度
- 150行代码总量，替代600+行
- "数据结构优先，消除特殊情况"
"""

import asyncio
import json
import time
import logging
from dataclasses import dataclass
from typing import Dict, AsyncGenerator, Literal, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SSEEvent:
    """统一SSE事件结构 - 核心数据结构1

    消除原有5种事件类的复杂性，统一为单一数据结构
    """

    type: Literal["connected", "progress", "completed", "error", "close"]
    task_id: str
    data: Dict[str, Any]
    timestamp: Optional[float] = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = time.time()

    def to_sse_format(self) -> str:
        """转换为SSE格式"""
        event_data = {
            "type": self.type,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            **self.data,
        }
        return f"data: {json.dumps(event_data)}\n\n"


class SSEService:
    """极简SSE服务 - 统一架构，消除分裂

    Linus原则实现：
    - 数据结构优先：task_id -> Queue映射
    - 消除特殊情况：统一的事件推送
    - 简洁胜过聪明：150行替代600+行
    """

    def __init__(self) -> None:
        # 核心数据结构2：连接注册表
        self.streams: Dict[str, asyncio.Queue[SSEEvent]] = {}
        # P0修复：添加并发安全保护
        self._lock = asyncio.Lock()
        logger.info(
            "SSEService initialized - unified architecture with concurrency safety"
        )

    async def push_event(
        self,
        event_type: Literal["connected", "progress", "completed", "error", "close"],
        task_id: str,
        **data: Any,
    ) -> None:
        """统一推送入口 - 消除所有特殊情况，带并发安全保护

        替代原有的notify_update和broadcast_task_update
        P0修复：添加并发锁和事件优先级处理

        Args:
            event_type: connected/progress/completed/error/close
            task_id: 任务ID
            **data: 事件特定数据
        """
        async with self._lock:
            if task_id in self.streams:
                event = SSEEvent(
                    type=event_type,
                    task_id=task_id,
                    data=data,
                )

                queue = self.streams[task_id]
                try:
                    queue.put_nowait(event)
                    logger.debug(f"Pushed {event_type} event for task {task_id}")
                except asyncio.QueueFull:
                    # P0修复：重要事件优先级处理
                    if event_type in ["completed", "error", "close"]:
                        # 为重要事件腾出空间：移除最老的心跳事件
                        try:
                            # 尝试移除队列中的心跳事件
                            temp_events = []
                            heartbeat_removed = False

                            # 检查队列中是否有心跳事件可以移除
                            for _ in range(min(10, queue.qsize())):
                                temp_event = queue.get_nowait()
                                if (
                                    not heartbeat_removed
                                    and temp_event.type == "progress"
                                    and temp_event.data.get("heartbeat")
                                ):
                                    heartbeat_removed = True
                                    logger.debug(
                                        f"Removed heartbeat to make room for {event_type}"
                                    )
                                else:
                                    temp_events.append(temp_event)

                            # 将非心跳事件放回队列
                            for temp_event in temp_events:
                                queue.put_nowait(temp_event)

                            # 如果成功移除心跳，再次尝试添加重要事件
                            if heartbeat_removed:
                                queue.put_nowait(event)
                                logger.info(
                                    f"Priority event {event_type} added for task {task_id}"
                                )
                            else:
                                logger.error(
                                    f"Failed to add critical event {event_type} for task {task_id}"
                                )

                        except asyncio.QueueEmpty:
                            logger.error(
                                f"Queue full, cannot add critical event {event_type} for task {task_id}"
                            )
                    else:
                        logger.warning(
                            f"Queue full for task {task_id}, dropping {event_type} event"
                        )
            else:
                logger.debug(f"No stream for task {task_id}, event ignored")

    async def stream(self, task_id: str) -> AsyncGenerator[str, None]:
        """极简流生成器 - 自动生命周期管理

        消除原有的复杂连接管理逻辑
        P0修复：加强资源管理和并发安全
        """
        # P0修复：并发安全的队列创建
        queue: asyncio.Queue[SSEEvent] = asyncio.Queue(maxsize=50)

        async with self._lock:
            self.streams[task_id] = queue

        try:
            # 发送连接确认事件
            connected_event = SSEEvent("connected", task_id, {"message": "连接已建立"})
            yield connected_event.to_sse_format()

            logger.info(f"SSE stream started for task {task_id}")

            while True:
                try:
                    # 等待事件，30秒超时发心跳
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event.to_sse_format()

                    # 终态自动断开
                    if event.type in ["completed", "error", "close"]:
                        break

                except asyncio.TimeoutError:
                    # 心跳事件
                    heartbeat = SSEEvent(
                        "progress", task_id, {"heartbeat": True, "message": "连接正常"}
                    )
                    yield heartbeat.to_sse_format()

        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for task {task_id}")
            raise

        except Exception as e:
            logger.error(f"SSE stream error for task {task_id}: {e}")
            # 发送错误事件
            error_event = SSEEvent("error", task_id, {"message": f"连接错误: {str(e)}"})
            yield error_event.to_sse_format()

        finally:
            # P0修复：并发安全的资源清理
            async with self._lock:
                if task_id in self.streams:
                    # 确保队列清空，避免内存泄漏
                    queue = self.streams.pop(task_id)
                    # 清空剩余事件
                    while not queue.empty():
                        try:
                            queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
            logger.info(f"SSE stream closed and cleaned for task {task_id}")

    def get_connection_count(self) -> int:
        """监控用：获取连接数"""
        return len(self.streams)

    def get_connected_tasks(self) -> list[str]:
        """调试用：获取活跃任务"""
        return list(self.streams.keys())


# 便捷方法 - 替代原有的复杂事件创建
# P0修复：异步便捷方法以支持并发安全
async def create_progress_event(task_id: str, progress: int, message: str) -> None:
    """创建进度事件 - 异步版本支持并发安全"""
    sse_service = get_sse_service()
    await sse_service.push_event(
        "progress", task_id, progress=progress, message=message
    )


async def create_completed_event(task_id: str, message: str = "任务完成") -> None:
    """创建完成事件 - 异步版本支持并发安全"""
    sse_service = get_sse_service()
    await sse_service.push_event("completed", task_id, message=message, progress=100)


async def create_error_event(task_id: str, message: str) -> None:
    """创建错误事件 - 异步版本支持并发安全"""
    sse_service = get_sse_service()
    await sse_service.push_event("error", task_id, message=message)


# 同步兼容接口（用于向后兼容）
def create_progress_event_sync(task_id: str, progress: int, message: str) -> None:
    """创建进度事件 - 同步兼容接口"""
    asyncio.create_task(create_progress_event(task_id, progress, message))


def create_completed_event_sync(task_id: str, message: str = "任务完成") -> None:
    """创建完成事件 - 同步兼容接口"""
    asyncio.create_task(create_completed_event(task_id, message))


def create_error_event_sync(task_id: str, message: str) -> None:
    """创建错误事件 - 同步兼容接口"""
    asyncio.create_task(create_error_event(task_id, message))


# 全局服务实例
_sse_service: Optional[SSEService] = None


def get_sse_service() -> SSEService:
    """获取全局SSE服务实例"""
    global _sse_service
    if _sse_service is None:
        _sse_service = SSEService()
    return _sse_service


# 使用示例：
#
# # 任务开始
# create_progress_event(task_id, 0, "任务开始")
#
# # 进度更新
# create_progress_event(task_id, 30, "正在采集数据")
#
# # 任务完成
# create_completed_event(task_id, "分析完成")
#
# # 任务失败
# create_error_event(task_id, "网络连接失败")
