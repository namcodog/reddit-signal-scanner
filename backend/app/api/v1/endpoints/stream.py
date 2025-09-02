"""
Reddit Signal Scanner - SSE极简推送端点 (统一架构版)

基于架构预审的150行极简实现：
- 消除架构分裂，统一SSE系统
- 2种核心数据结构，替代5种复杂类
- 统一事件处理，消除特殊情况
- 自动生命周期管理，简洁胜过聪明
"""

import asyncio
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ....core.sse import (
    get_sse_service,
    create_progress_event,
    create_completed_event,
    create_error_event,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stream", tags=["实时推送"])


async def generate_mock_events(task_id: str) -> AsyncGenerator[str, None]:
    """
    生成Mock任务事件流 - 极简版本

    基于统一SSE架构，消除复杂事件类型
    """
    # Mock事件序列 - 简化为进度数据
    mock_steps = [
        (0, "任务开始"),
        (15, "连接Reddit API"),
        (30, "采集帖子数据"),
        (50, "采集评论数据"),
        (70, "情感分析处理"),
        (90, "生成洞察报告"),
        (100, "分析完成"),
    ]

    try:
        # 异步推送Mock更新
        for progress, message in mock_steps:
            if progress < 100:
                await create_progress_event(task_id, progress, message)
            else:
                await create_completed_event(task_id, message)
            await asyncio.sleep(2)  # 模拟处理时间

        # 使用统一SSE服务生成流
        sse_service = get_sse_service()
        async for event in sse_service.stream(task_id):
            yield event

    except Exception as e:
        # 推送错误事件
        await create_error_event(task_id, f"Mock事件生成失败: {str(e)}")

        # 生成错误流
        sse_service = get_sse_service()
        async for event in sse_service.stream(task_id):
            yield event


async def create_sse_stream(task_id: str) -> AsyncGenerator[str, None]:
    """创建SSE流生成器 - 极简统一架构

    基于架构预审的简化设计：
    - 直接使用统一SSE服务
    - 自动生命周期管理
    - 消除复杂的连接逻辑
    """
    sse_service = get_sse_service()

    try:
        logger.info(f"SSE stream started for task {task_id}")

        # 直接使用统一服务生成流
        async for event in sse_service.stream(task_id):
            yield event

    except Exception as e:
        logger.error(f"SSE stream error for task {task_id}: {e}")
        # 推送错误事件
        await create_error_event(task_id, f"连接错误: {str(e)}")


@router.get("/{task_id}", summary="SSE任务状态推送 - 统一架构版")
async def stream_task_status(task_id: str) -> StreamingResponse:
    """
    SSE实时推送任务状态 - 基于架构预审的极简实现

    统一设计原则：
    - 消除架构分裂，单一SSE系统
    - 2种核心数据结构，简洁明了
    - 统一事件格式，消除特殊情况

    客户端示例：
    ```javascript
    const eventSource = new EventSource('/api/v1/stream/{task_id}');
    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        console.log(`${data.type}: ${data.progress}% - ${data.message}`);
    };
    ```

    返回格式 (统一JSON):
    ```json
    {
        "type": "connected|progress|completed|error|close",
        "task_id": "uuid",
        "timestamp": 1640995200,
        "progress": 50,
        "message": "正在分析数据..."
    }
    ```
    """
    # 简化参数验证
    if not task_id or len(task_id) < 4:
        raise HTTPException(status_code=400, detail="Invalid task_id")

    logger.info(f"Starting unified SSE stream for task: {task_id}")

    return StreamingResponse(
        create_sse_stream(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{task_id}/test", summary="测试SSE连接")
async def test_stream(task_id: str) -> StreamingResponse:
    """
    测试SSE连接是否正常 - 极简版

    发送3个测试事件后关闭连接
    """

    async def test_events() -> AsyncGenerator[str, None]:
        try:
            # 发送3个测试事件
            test_steps = [
                (33, "测试连接 1/3"),
                (66, "测试连接 2/3"),
                (100, "测试连接完成"),
            ]

            for progress, message in test_steps:
                if progress < 100:
                    await create_progress_event(task_id, progress, message)
                else:
                    await create_completed_event(task_id, message)
                await asyncio.sleep(1)

            # 使用统一SSE服务生成流
            sse_service = get_sse_service()
            async for event in sse_service.stream(task_id):
                yield event

        except Exception as e:
            logger.error(f"Test stream error: {e}")
            await create_error_event(task_id, f"测试失败: {str(e)}")

    return StreamingResponse(
        test_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/{task_id}/mock", summary="Mock任务流演示")
async def mock_stream(task_id: str) -> StreamingResponse:
    """
    Mock任务流演示 - 完整的分析流程模拟

    演示完整的Reddit信号分析流程，基于统一SSE架构
    """
    logger.info(f"Starting mock stream for task: {task_id}")

    return StreamingResponse(
        generate_mock_events(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )
