#!/usr/bin/env python3
"""
集成测试脚本 - 验证v0界面和Mock API的完整集成
"""

import asyncio
import sys
import time
from pathlib import Path

# 添加backend到Python路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.services.mock.reddit_mock_service import RedditMockService
from app.api.v1.endpoints.mock_discovery import (
    create_mock_analysis,
    get_mock_task_status,
    get_mock_analysis_result,
    MockAnalysisRequest,
    BackgroundTasks
)


async def test_mock_service():
    """测试Mock Reddit服务"""
    print("\n=== 测试Mock Reddit服务 ===")
    
    service = RedditMockService()
    
    # 测试获取社区帖子
    posts = await service.get_community_posts("entrepreneur", limit=5)
    print(f"✓ 获取到 {len(posts)} 个帖子")
    
    if posts:
        first_post = posts[0]
        print(f"  - 标题: {first_post.title[:50]}...")
        print(f"  - 社区: {first_post.community}")
        print(f"  - 得分: {first_post.score}")
    
    # 测试搜索功能
    search_results = await service.search_posts("tool", limit=3)
    print(f"✓ 搜索到 {len(search_results)} 个相关帖子")
    
    return True


async def test_mock_api():
    """测试Mock API端点"""
    print("\n=== 测试Mock API端点 ===")
    
    # 创建后台任务（模拟FastAPI的BackgroundTasks）
    class MockBackgroundTasks(BackgroundTasks):
        def __init__(self):
            self.tasks = []
        
        def add_task(self, func, *args, **kwargs):
            # 在测试中直接运行任务
            task = asyncio.create_task(func(*args, **kwargs))
            self.tasks.append(task)
    
    background_tasks = MockBackgroundTasks()
    
    # 创建分析请求
    request = MockAnalysisRequest(
        description="一个帮助远程团队管理项目的SaaS工具，集成Slack并自动跟踪任务时间",
        urgent=False
    )
    
    # 创建分析任务
    response = await create_mock_analysis(request, background_tasks)
    task_id = response.task_id
    print(f"✓ 创建分析任务: {task_id}")
    
    # 等待后台任务开始
    await asyncio.sleep(1)
    
    # 检查任务状态
    max_attempts = 10
    for i in range(max_attempts):
        status = await get_mock_task_status(task_id)
        print(f"  状态 [{i+1}/{max_attempts}]: {status['status']} (进度: {status['progress']}%)")
        
        if status['status'] == 'completed':
            break
        
        await asyncio.sleep(1)
    
    # 获取分析结果
    if status['status'] == 'completed':
        result = await get_mock_analysis_result(task_id)
        print(f"✓ 获取分析结果成功")
        print(f"  - 机会数量: {len(result['opportunities'])}")
        print(f"  - 置信度: {result['confidence_score']:.2f}")
        
        if result['opportunities']:
            opp = result['opportunities'][0]
            print(f"  - 首要机会: {opp['title']}")
            print(f"    信心: {opp['confidence']}")
            print(f"    市场规模: {opp['market_size']}")
    
    # 等待所有后台任务完成
    if background_tasks.tasks:
        await asyncio.gather(*background_tasks.tasks)
    
    return True


async def main():
    """主测试函数"""
    print("=" * 60)
    print("Reddit Signal Scanner - v0界面集成测试")
    print("=" * 60)
    
    try:
        # 测试Mock服务
        mock_service_ok = await test_mock_service()
        
        # 测试Mock API
        mock_api_ok = await test_mock_api()
        
        print("\n" + "=" * 60)
        if mock_service_ok and mock_api_ok:
            print("✅ 所有测试通过！")
            print("\n下一步:")
            print("1. 启动后端服务: cd backend && uvicorn app.main:app --reload")
            print("2. 启动前端服务: cd frontend && npm run dev")
            print("3. 访问 http://localhost:5173 测试完整流程")
        else:
            print("❌ 部分测试失败，请检查错误信息")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    # 运行异步测试
    success = asyncio.run(main())
    sys.exit(0 if success else 1)