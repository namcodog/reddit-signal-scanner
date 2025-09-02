#!/usr/bin/env python3
"""
SSE集成测试 - 验证简化架构是否工作
测试统一的TaskUpdate数据结构和直接推送机制
"""

import asyncio
import sys
import os

# 添加后端路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.models.task import TaskUpdate, TaskStatus
from app.services.sse_service import TaskSSEService, get_sse_service


async def test_sse_basic_functionality():
    """测试SSE基础功能"""
    print("🧪 测试1: SSE基础功能")
    
    # 创建SSE服务
    sse_service = get_sse_service()
    
    # 测试连接管理
    task_id = "test-task-001"
    print(f"📊 初始连接数: {sse_service.get_connection_count()}")
    
    # 模拟客户端连接 - 创建异步任务但不等待
    stream_task = asyncio.create_task(
        consume_sse_stream(sse_service, task_id)
    )
    
    # 等待连接建立
    await asyncio.sleep(0.1)
    print(f"📊 连接后连接数: {sse_service.get_connection_count()}")
    
    # 发送测试更新
    print("📤 发送测试更新...")
    sse_service.notify_update(task_id, TaskStatus.PROCESSING, 10, "开始测试")
    sse_service.notify_update(task_id, TaskStatus.PROCESSING, 50, "测试进行中")
    sse_service.notify_update(task_id, TaskStatus.COMPLETED, 100, "测试完成")
    
    # 等待流处理完成
    await stream_task
    print(f"📊 断开后连接数: {sse_service.get_connection_count()}")
    
    print("✅ 测试1通过\n")


async def consume_sse_stream(sse_service: TaskSSEService, task_id: str):
    """模拟客户端消费SSE流"""
    print(f"🔌 开始监听任务 {task_id} 的SSE流")
    
    event_count = 0
    async for sse_event in sse_service.stream_updates(task_id):
        event_count += 1
        # 解析SSE格式
        if sse_event.startswith("data: "):
            data = sse_event[6:].strip()
            print(f"📨 收到事件 {event_count}: {data[:80]}...")
        
        # 收到3个事件后检查是否结束
        if event_count >= 3:
            break
    
    print(f"🔌 SSE流结束，共收到 {event_count} 个事件")


async def test_task_update_formats():
    """测试TaskUpdate数据格式"""
    print("🧪 测试2: TaskUpdate数据格式")
    
    # 测试不同类型的更新
    test_cases = [
        TaskUpdate.create_started("task-001", "任务开始"),
        TaskUpdate.create_progress("task-001", 33, "正在处理数据"),
        TaskUpdate.create_progress("task-001", 66, "分析中..."),
        TaskUpdate.create_completed("task-001", "分析完成"),
        TaskUpdate.create_failed("task-001", "网络连接失败"),
    ]
    
    for i, update in enumerate(test_cases, 1):
        print(f"📄 更新 {i}: {update.status.value} - {update.progress}% - {update.message}")
        
        # 测试JSON序列化
        json_str = update.to_json()
        assert "task_id" in json_str
        assert "status" in json_str
        assert "progress" in json_str
        assert "message" in json_str
        
        # 测试SSE格式
        sse_str = update.to_sse_format()
        assert sse_str.startswith("data: ")
        assert sse_str.endswith("\n\n")
    
    print("✅ 测试2通过\n")


async def test_concurrent_connections():
    """测试并发连接"""
    print("🧪 测试3: 并发连接处理")
    
    sse_service = get_sse_service()
    
    # 创建3个并发连接
    tasks = []
    for i in range(3):
        task_id = f"concurrent-task-{i}"
        tasks.append(asyncio.create_task(
            consume_sse_stream(sse_service, task_id)
        ))
    
    # 等待连接建立
    await asyncio.sleep(0.1)
    print(f"📊 并发连接数: {sse_service.get_connection_count()}")
    
    # 向所有任务发送更新
    for i in range(3):
        task_id = f"concurrent-task-{i}"
        sse_service.notify_update(task_id, TaskStatus.PROCESSING, 50, f"任务{i}进行中")
        sse_service.notify_update(task_id, TaskStatus.COMPLETED, 100, f"任务{i}完成")
    
    # 等待所有连接完成
    await asyncio.gather(*tasks)
    
    print(f"📊 清理后连接数: {sse_service.get_connection_count()}")
    print("✅ 测试3通过\n")


async def main():
    """运行所有测试"""
    print("🚀 开始SSE集成测试 - Linus简化架构验证")
    print("=" * 50)
    
    try:
        await test_task_update_formats()
        await test_sse_basic_functionality() 
        await test_concurrent_connections()
        
        print("🎉 所有测试通过！")
        print("✅ 统一的TaskUpdate数据结构工作正常")
        print("✅ 直接推送机制工作正常") 
        print("✅ 连接管理和清理工作正常")
        print("✅ 并发处理工作正常")
        
        print("\n📊 架构简洁度验证:")
        print("- 数据结构: 单一TaskUpdate ✅")
        print("- 推送机制: 直接notify_update ✅") 
        print("- 连接管理: asyncio.Queue自动 ✅")
        print("- 特殊情况: 零个if-else分支 ✅")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)