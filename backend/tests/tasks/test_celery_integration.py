"""
prd04-08: Celery集成就绪性测试（Context7最小实现）
"""
from typing import Any
import os
import pytest
from pytest_celery import CeleryTestSetup


class TestCeleryIntegration:
    @pytest.mark.skipif(
        os.getenv("CONTEXT7_USE_LOCAL_WORKER") == "1",
        reason="Use local worker fallback",
    )
    def test_environment_ready_context7(self, celery_setup: CeleryTestSetup) -> None:
        assert celery_setup.ready()
        assert celery_setup.broker is not None
        assert celery_setup.backend is not None
        assert celery_setup.worker is not None

    @pytest.mark.skipif(
        os.getenv("CONTEXT7_USE_LOCAL_WORKER") != "1",
        reason="Only run in local worker mode",
    )
    def test_environment_ready_local(
        self, celery_app_instance: Any, local_celery_worker: Any
    ) -> None:
        assert celery_app_instance is not None
        # local_celery_worker is a context manager from fixture yield
        assert local_celery_worker is not None

    @pytest.mark.skipif(
        os.getenv("CONTEXT7_USE_LOCAL_WORKER") == "1",
        reason="Use local worker fallback",
    )
    def test_health_check_task_context7(self, celery_setup: CeleryTestSetup) -> None:
        from app.tasks.analysis_tasks import analysis_health_check

        result = analysis_health_check.delay()
        value = result.get(timeout=30)
        assert result.successful()
        if isinstance(value, dict):
            assert value.get("status") == "healthy"
        else:
            assert hasattr(value, "status") and value.status == "healthy"

    @pytest.mark.skipif(
        os.getenv("CONTEXT7_USE_LOCAL_WORKER") != "1",
        reason="Only run in local worker mode",
    )
    def test_health_check_task_local(
        self, celery_app_instance: Any, local_celery_worker: Any
    ) -> None:
        from app.tasks.analysis_tasks import analysis_health_check

        result = analysis_health_check.delay()
        value = result.get(timeout=30)
        assert result.successful()
        if isinstance(value, dict):
            assert value.get("status") == "healthy"
        else:
            assert hasattr(value, "status") and value.status == "healthy"
