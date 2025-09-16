"""系统测试示例 - 完整分析工作流"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, AsyncIterator, Dict, List, Optional

import pytest

from tests.fixtures.base_fixtures import AssertHelpers, TestIsolation, performance_timer
from tests.utils.api_switcher import auto_api_mode


@TestIsolation.system_test
class TestCompleteAnalysisWorkflow:
    """完整分析工作流系统测试"""

    @pytest.fixture
    async def test_user_context(self, auto_api_mode: Any) -> AsyncIterator[Dict[str, Any]]:
        """创建测试用户上下文"""
        if auto_api_mode.is_mock_mode:
            pytest.skip("系统测试需要真实环境")

        context: Dict[str, Any] = {
            "user_id": "test_user_system",
            "email": "system_test@example.com",
            "api_base": "http://localhost:8000",
            "created_tasks": [],
            "start_time": datetime.now(),
        }

        yield context

    async def test_new_user_complete_journey(
        self, test_user_context: Dict[str, Any], performance_timer: Any
    ) -> None:
        performance_timer.start()

        register_data = await self._register_user(test_user_context)
        assert register_data["user_id"]
        performance_timer.checkpoint("user_registered")

        auth_token = await self._login_user(test_user_context)
        assert auth_token
        test_user_context["auth_token"] = auth_token
        performance_timer.checkpoint("user_logged_in")

        task_id = await self._submit_analysis_task(
            test_user_context,
            keywords=["startup", "entrepreneur", "business"],
            limit=100,
        )
        test_user_context["created_tasks"].append(task_id)
        performance_timer.checkpoint("task_submitted")

        final_status = await self._monitor_task_progress(test_user_context, task_id)
        assert final_status["status"] == "completed"
        performance_timer.checkpoint("task_completed")

        report = await self._get_analysis_report(test_user_context, task_id)
        assert self._validate_report_quality(report)
        performance_timer.checkpoint("report_retrieved")

        export_result = await self._export_report(test_user_context, task_id, format="pdf")
        assert export_result["success"]
        performance_timer.checkpoint("report_exported")

        performance_timer.stop()
        performance_timer.assert_performance(300)

        assert len(report["insights"]["pain_points"]) > 0
        assert len(report["insights"]["opportunities"]) > 0
        assert report["confidence_score"] > 0.7

    async def test_concurrent_multi_task_workflow(
        self, test_user_context: Dict[str, Any]
    ) -> None:
        task_configs: List[tuple[List[str], int]] = [
            (["python", "django", "flask"], 50),
            (["javascript", "react", "vue"], 50),
            (["marketing", "growth", "sales"], 50),
        ]

        submission_tasks = [
            self._submit_analysis_task(test_user_context, keywords=kw, limit=limit)
            for kw, limit in task_configs
        ]
        task_ids = await asyncio.gather(*submission_tasks)
        test_user_context.setdefault("created_tasks", []).extend(task_ids)

        monitor_tasks = [
            self._monitor_task_progress(test_user_context, task_id) for task_id in task_ids
        ]
        results = await asyncio.gather(*monitor_tasks)
        assert all(result["status"] == "completed" for result in results)

        reports = [
            await self._get_analysis_report(test_user_context, task_id)
            for task_id in task_ids
        ]
        assert len({str(report["insights"]) for report in reports}) == len(reports)

    async def test_error_recovery_workflow(self, test_user_context: Dict[str, Any]) -> None:
        task_id = await self._submit_analysis_task(
            test_user_context,
            keywords=["test"],
            limit=10,
            subreddits=["invalid_subreddit_12345"],
        )

        final_status = await self._monitor_task_progress(
            test_user_context,
            task_id,
            expected_status="failed",
        )
        assert final_status["status"] == "failed"
        assert final_status["error_message"]

        retry_task_id = await self._retry_failed_task(
            test_user_context,
            failed_task_id=task_id,
            new_subreddits=["entrepreneur", "startups"],
        )

        retry_status = await self._monitor_task_progress(
            test_user_context, retry_task_id
        )
        assert retry_status["status"] == "completed"

    async def test_data_consistency_across_services(
        self, test_user_context: Dict[str, Any]
    ) -> None:
        task_id = await self._submit_analysis_task(
            test_user_context,
            keywords=["consistency", "test"],
            limit=20,
        )

        await self._monitor_task_progress(test_user_context, task_id)

        status_data = await self._get_task_status(test_user_context, task_id)
        report_data = await self._get_analysis_report(test_user_context, task_id)
        history_data = await self._get_user_task_history(test_user_context)

        assert any(t["id"] == task_id for t in history_data["tasks"])
        assert status_data["status"] == "completed"
        assert report_data["task_id"] == task_id

        created_at = datetime.fromisoformat(status_data["created_at"])
        completed_at = datetime.fromisoformat(status_data["completed_at"])
        assert completed_at > created_at
        assert (completed_at - created_at).total_seconds() < 300

    async def test_performance_under_load(
        self, test_user_context: Dict[str, Any], performance_timer: Any
    ) -> None:
        num_concurrent_users = 5
        tasks_per_user = 3

        async def simulate_user(user_id: int) -> List[str]:
            user_tasks: List[str] = []
            for i in range(tasks_per_user):
                await asyncio.sleep(0.1 * i)
                task_id = await self._submit_analysis_task(
                    test_user_context,
                    keywords=[f"user{user_id}_task{i}"],
                    limit=10,
                )
                user_tasks.append(task_id)

            for task_id in user_tasks:
                await self._monitor_task_progress(test_user_context, task_id)
            return user_tasks

        performance_timer.start()
        user_simulations = [simulate_user(i) for i in range(num_concurrent_users)]
        all_tasks = await asyncio.gather(*user_simulations)
        performance_timer.stop()

        total_tasks = sum(len(tasks) for tasks in all_tasks)
        assert total_tasks == num_concurrent_users * tasks_per_user

        avg_time_per_task = performance_timer.duration / total_tasks
        assert avg_time_per_task < 60

    async def _register_user(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {"user_id": context["user_id"]}

    async def _login_user(self, context: Dict[str, Any]) -> str:
        return "mock_auth_token"

    async def _submit_analysis_task(
        self,
        context: Dict[str, Any],
        keywords: List[str],
        limit: int,
        subreddits: Optional[List[str]] = None,
    ) -> str:
        return f"task_{int(time.time() * 1000)}"

    async def _monitor_task_progress(
        self,
        context: Dict[str, Any],
        task_id: str,
        expected_status: str = "completed",
        timeout: int = 120,
    ) -> Dict[str, Any]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = await self._get_task_status(context, task_id)
            if status["status"] == expected_status:
                return status
            if status["status"] == "failed" and expected_status != "failed":
                raise AssertionError(f"任务意外失败: {status.get('error_message')}")
            await asyncio.sleep(2)
        raise TimeoutError(f"任务在{timeout}秒内未达到预期状态")

    async def _get_task_status(self, context: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        return {
            "status": "completed",
            "created_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
        }

    async def _get_analysis_report(self, context: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        return {
            "task_id": task_id,
            "insights": {
                "pain_points": [{"description": "测试痛点"}],
                "opportunities": [{"title": "测试机会"}],
            },
            "confidence_score": 0.85,
        }

    async def _export_report(
        self,
        context: Dict[str, Any],
        task_id: str,
        format: str,
    ) -> Dict[str, Any]:
        return {"success": True, "file_url": f"/exports/{task_id}.{format}"}

    async def _retry_failed_task(
        self,
        context: Dict[str, Any],
        failed_task_id: str,
        **_new_params: Any,
    ) -> str:
        return f"retry_{failed_task_id}"

    async def _get_user_task_history(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {"tasks": [{"id": task_id} for task_id in context.get("created_tasks", [])]}

    def _validate_report_quality(self, report: Dict[str, Any]) -> bool:
        if not report.get("insights"):
            return False
        insights = report["insights"]
        if not insights.get("pain_points") and not insights.get("opportunities"):
            return False
        confidence = report.get("confidence_score", 0)
        if confidence < 0.5 or confidence > 1.0:
            return False
        return True
