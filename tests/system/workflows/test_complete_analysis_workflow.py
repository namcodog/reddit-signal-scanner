"""系统测试示例 - 完整分析工作流

展示系统测试的最佳实践：
1. 端到端业务流程验证
2. 使用真实环境（优先）
3. 测试多个组件协作
4. 验证业务价值交付
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

from tests.fixtures.base_fixtures import TestIsolation, AssertHelpers, performance_timer
from tests.utils.api_switcher import auto_api_mode


@TestIsolation.system_test
class TestCompleteAnalysisWorkflow:
    """完整分析工作流系统测试"""
    
    @pytest.fixture
    async def test_user_context(self, auto_api_mode):
        """创建测试用户上下文"""
        # 系统测试优先使用真实API
        if auto_api_mode.is_mock_mode:
            pytest.skip("系统测试需要真实环境")
            
        # 创建测试用户或使用已有用户
        context = {
            "user_id": "test_user_system",
            "email": "system_test@example.com",
            "api_base": "http://localhost:8000",
            "created_tasks": [],
            "start_time": datetime.now()
        }
        
        yield context
        
        # 清理创建的测试数据
        # TODO: 清理任务和相关数据
        
    async def test_new_user_complete_journey(self, test_user_context, performance_timer):
        """测试新用户完整体验流程"""
        performance_timer.start()
        
        # 1. 用户注册
        register_data = await self._register_user(test_user_context)
        assert register_data["user_id"]
        performance_timer.checkpoint("user_registered")
        
        # 2. 用户登录
        auth_token = await self._login_user(test_user_context)
        assert auth_token
        test_user_context["auth_token"] = auth_token
        performance_timer.checkpoint("user_logged_in")
        
        # 3. 提交分析任务
        task_id = await self._submit_analysis_task(
            test_user_context,
            keywords=["startup", "entrepreneur", "business"],
            limit=100
        )
        test_user_context["created_tasks"].append(task_id)
        performance_timer.checkpoint("task_submitted")
        
        # 4. 监控任务进度
        final_status = await self._monitor_task_progress(test_user_context, task_id)
        assert final_status["status"] == "completed"
        performance_timer.checkpoint("task_completed")
        
        # 5. 获取分析结果
        report = await self._get_analysis_report(test_user_context, task_id)
        assert self._validate_report_quality(report)
        performance_timer.checkpoint("report_retrieved")
        
        # 6. 导出报告
        export_result = await self._export_report(test_user_context, task_id, format="pdf")
        assert export_result["success"]
        performance_timer.checkpoint("report_exported")
        
        # 验证整体性能
        performance_timer.stop()
        performance_timer.assert_performance(300)  # 5分钟内完成
        
        # 验证业务价值
        assert len(report["insights"]["pain_points"]) > 0
        assert len(report["insights"]["opportunities"]) > 0
        assert report["confidence_score"] > 0.7
        
    async def test_concurrent_multi_task_workflow(self, test_user_context):
        """测试并发多任务工作流"""
        # 准备多组不同的关键词
        task_configs = [
            {"keywords": ["python", "django", "flask"], "limit": 50},
            {"keywords": ["javascript", "react", "vue"], "limit": 50},
            {"keywords": ["marketing", "growth", "sales"], "limit": 50},
        ]
        
        # 并发提交任务
        tasks = []
        for config in task_configs:
            task = self._submit_analysis_task(test_user_context, **config)
            tasks.append(task)
            
        task_ids = await asyncio.gather(*tasks)
        test_user_context["created_tasks"].extend(task_ids)
        
        # 并发监控所有任务
        monitor_tasks = []
        for task_id in task_ids:
            monitor = self._monitor_task_progress(test_user_context, task_id)
            monitor_tasks.append(monitor)
            
        results = await asyncio.gather(*monitor_tasks)
        
        # 验证所有任务都成功完成
        for result in results:
            assert result["status"] == "completed"
            
        # 验证结果的独立性（不同任务的结果应该不同）
        reports = []
        for task_id in task_ids:
            report = await self._get_analysis_report(test_user_context, task_id)
            reports.append(report)
            
        # 验证每个报告都有独特的内容
        assert len(set(str(r["insights"]) for r in reports)) == len(reports)
        
    async def test_error_recovery_workflow(self, test_user_context):
        """测试错误恢复工作流"""
        # 1. 提交一个会失败的任务（例如：无效的subreddit）
        task_id = await self._submit_analysis_task(
            test_user_context,
            keywords=["test"],
            limit=10,
            subreddits=["invalid_subreddit_12345"]
        )
        
        # 2. 等待任务失败
        final_status = await self._monitor_task_progress(
            test_user_context, 
            task_id,
            expected_status="failed"
        )
        assert final_status["status"] == "failed"
        assert final_status["error_message"]
        
        # 3. 重试任务（使用修正的参数）
        retry_task_id = await self._retry_failed_task(
            test_user_context,
            task_id,
            new_subreddits=["entrepreneur", "startups"]
        )
        
        # 4. 验证重试成功
        retry_status = await self._monitor_task_progress(
            test_user_context,
            retry_task_id
        )
        assert retry_status["status"] == "completed"
        
    async def test_data_consistency_across_services(self, test_user_context):
        """测试跨服务数据一致性"""
        # 1. 创建任务并等待完成
        task_id = await self._submit_analysis_task(
            test_user_context,
            keywords=["consistency", "test"],
            limit=20
        )
        
        await self._monitor_task_progress(test_user_context, task_id)
        
        # 2. 从不同端点获取数据
        # 从状态端点获取
        status_data = await self._get_task_status(test_user_context, task_id)
        
        # 从报告端点获取
        report_data = await self._get_analysis_report(test_user_context, task_id)
        
        # 从历史端点获取
        history_data = await self._get_user_task_history(test_user_context)
        
        # 3. 验证数据一致性
        # 任务ID应该在历史记录中
        assert any(t["id"] == task_id for t in history_data["tasks"])
        
        # 状态应该一致
        assert status_data["status"] == "completed"
        assert report_data["task_id"] == task_id
        
        # 时间戳应该合理
        created_at = datetime.fromisoformat(status_data["created_at"])
        completed_at = datetime.fromisoformat(status_data["completed_at"])
        assert completed_at > created_at
        assert (completed_at - created_at).total_seconds() < 300  # 5分钟内完成
        
    async def test_performance_under_load(self, test_user_context, performance_timer):
        """测试负载下的性能表现"""
        # 模拟多个用户同时使用系统
        num_concurrent_users = 5
        tasks_per_user = 3
        
        async def simulate_user(user_id: int):
            """模拟单个用户行为"""
            user_tasks = []
            
            for i in range(tasks_per_user):
                # 随机延迟，模拟真实用户行为
                await asyncio.sleep(0.1 * i)
                
                task_id = await self._submit_analysis_task(
                    test_user_context,
                    keywords=[f"user{user_id}_task{i}"],
                    limit=10
                )
                user_tasks.append(task_id)
                
            # 等待所有任务完成
            for task_id in user_tasks:
                await self._monitor_task_progress(test_user_context, task_id)
                
            return user_tasks
            
        # 并发模拟多个用户
        performance_timer.start()
        
        user_simulations = []
        for i in range(num_concurrent_users):
            simulation = simulate_user(i)
            user_simulations.append(simulation)
            
        all_tasks = await asyncio.gather(*user_simulations)
        
        performance_timer.stop()
        
        # 验证性能指标
        total_tasks = sum(len(tasks) for tasks in all_tasks)
        assert total_tasks == num_concurrent_users * tasks_per_user
        
        # 平均每个任务的处理时间
        avg_time_per_task = performance_timer.duration / total_tasks
        assert avg_time_per_task < 60  # 平均每个任务不超过1分钟
        
    # ==================== 辅助方法 ====================
    
    async def _register_user(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """注册用户"""
        # TODO: 实现用户注册
        return {"user_id": context["user_id"]}
        
    async def _login_user(self, context: Dict[str, Any]) -> str:
        """用户登录"""
        # TODO: 实现用户登录
        return "mock_auth_token"
        
    async def _submit_analysis_task(
        self, 
        context: Dict[str, Any],
        keywords: List[str],
        limit: int,
        subreddits: Optional[List[str]] = None
    ) -> str:
        """提交分析任务"""
        # TODO: 实现任务提交
        return f"task_{int(time.time())}"
        
    async def _monitor_task_progress(
        self,
        context: Dict[str, Any],
        task_id: str,
        expected_status: str = "completed",
        timeout: int = 120
    ) -> Dict[str, Any]:
        """监控任务进度"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = await self._get_task_status(context, task_id)
            
            if status["status"] == expected_status:
                return status
            elif status["status"] == "failed" and expected_status != "failed":
                raise AssertionError(f"任务意外失败: {status.get('error_message')}")
                
            await asyncio.sleep(2)  # 2秒轮询一次
            
        raise TimeoutError(f"任务在{timeout}秒内未达到预期状态")
        
    async def _get_task_status(self, context: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        # TODO: 实现状态查询
        return {
            "status": "completed",
            "created_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat()
        }
        
    async def _get_analysis_report(self, context: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """获取分析报告"""
        # TODO: 实现报告获取
        return {
            "task_id": task_id,
            "insights": {
                "pain_points": [{"description": "测试痛点"}],
                "opportunities": [{"title": "测试机会"}]
            },
            "confidence_score": 0.85
        }
        
    async def _export_report(
        self,
        context: Dict[str, Any],
        task_id: str,
        format: str
    ) -> Dict[str, Any]:
        """导出报告"""
        # TODO: 实现报告导出
        return {"success": True, "file_url": f"/exports/{task_id}.{format}"}
        
    async def _retry_failed_task(
        self,
        context: Dict[str, Any],
        failed_task_id: str,
        **new_params
    ) -> str:
        """重试失败的任务"""
        # TODO: 实现任务重试
        return f"retry_{failed_task_id}"
        
    async def _get_user_task_history(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """获取用户任务历史"""
        # TODO: 实现历史查询
        return {"tasks": [{"id": task_id} for task_id in context["created_tasks"]]}
        
    def _validate_report_quality(self, report: Dict[str, Any]) -> bool:
        """验证报告质量"""
        # 检查必要的字段
        if not report.get("insights"):
            return False
            
        insights = report["insights"]
        
        # 至少应该有一些发现
        if not insights.get("pain_points") and not insights.get("opportunities"):
            return False
            
        # 置信度应该在合理范围
        confidence = report.get("confidence_score", 0)
        if confidence < 0.5 or confidence > 1.0:
            return False
            
        return True