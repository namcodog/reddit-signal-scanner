"""
prd04-08: 性能基线最小验证（Context7最小实现）
"""
import os
import time
import pytest
from typing import Any
from pytest_celery import CeleryTestSetup


class TestPerformanceBaseline:
    @pytest.mark.skipif(
        os.getenv("CONTEXT7_USE_LOCAL_WORKER") == "1",
        reason="Use local worker fallback",
    )
    def test_submit_5_health_checks_under_30s_context7(
        self, celery_setup: CeleryTestSetup
    ) -> None:
        from app.tasks.analysis_tasks import analysis_health_check

        start = time.time()
        results = [analysis_health_check.delay() for _ in range(5)]

        completed = 0
        for r in results:
            try:
                _ = r.get(timeout=30)
                if r.successful():
                    completed += 1
            except Exception:
                pass

        elapsed = time.time() - start
        assert (
            completed >= 3 and elapsed < 30
        ), f"completed={completed}, elapsed={elapsed:.2f}s"

    @pytest.mark.skipif(
        os.getenv("CONTEXT7_USE_LOCAL_WORKER") != "1",
        reason="Only run in local worker mode",
    )
    def test_submit_5_health_checks_under_30s_local(
        self, celery_app_instance: Any, local_celery_worker: Any
    ) -> None:
        from app.tasks.analysis_tasks import analysis_health_check

        start = time.time()
        results = [analysis_health_check.delay() for _ in range(5)]

        completed = 0
        for r in results:
            try:
                _ = r.get(timeout=30)
                if r.successful():
                    completed += 1
            except Exception:
                pass

        elapsed = time.time() - start
        assert (
            completed >= 3 and elapsed < 30
        ), f"completed={completed}, elapsed={elapsed:.2f}s"
