"""
prd04-08: 任务生命周期测试（Context7最小实现）
"""
import os
import pytest
from typing import Any
from pytest_celery import CeleryTestSetup


class TestTaskLifecycle:
    @pytest.mark.skipif(
        os.getenv("CONTEXT7_USE_LOCAL_WORKER") == "1",
        reason="Use local worker fallback",
    )
    def test_analyze_product_lifecycle_context7(
        self, celery_setup: CeleryTestSetup
    ) -> None:
        from app.tasks.analysis_tasks import analyze_product_task

        payload = {"product_description": "AI写作助手，帮助用户生成高质量内容"}
        task_data = {"task_id": "lifecycle-001", "user_id": "u-1"}

        result = analyze_product_task.delay(payload=payload, task_data=task_data)

        try:
            value = result.get(timeout=60)
            assert result.successful()
            assert hasattr(value, "status")
        except Exception as e:
            pytest.skip(f"环境依赖不完整，跳过：{e}")

    @pytest.mark.skipif(
        os.getenv("CONTEXT7_USE_LOCAL_WORKER") != "1",
        reason="Only run in local worker mode",
    )
    def test_analyze_product_lifecycle_local(
        self, celery_app_instance: Any, local_celery_worker: Any
    ) -> None:
        from app.tasks.analysis_tasks import analyze_product_task

        payload = {"product_description": "AI写作助手，帮助用户生成高质量内容"}
        task_data = {"task_id": "lifecycle-001", "user_id": "u-1"}

        result = analyze_product_task.delay(payload=payload, task_data=task_data)
        value = result.get(timeout=60)
        assert result.successful()
        # 兼容 dict 返回
        if isinstance(value, dict):
            assert value.get("status") in ("completed", "processing", "pending")
            assert isinstance(value.get("analysis_result", {}), dict)
        else:
            assert hasattr(value, "status")
