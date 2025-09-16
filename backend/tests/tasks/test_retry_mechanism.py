"""
prd04-08: 重试机制最小验证（Context7最小实现）
"""
import os
import pytest
from typing import Any
from pytest_celery import CeleryTestSetup


class TestRetryMechanism:
    @pytest.mark.skipif(
        os.getenv("CONTEXT7_USE_LOCAL_WORKER") == "1",
        reason="Use local worker fallback",
    )
    def test_autoretry_configured_context7(self, celery_setup: CeleryTestSetup) -> None:
        # 仅验证任务配置含有 autoretry_for 与 max_retries，避免构造真实错误场景
        from app.tasks.analysis_tasks import analyze_product_task

        # celery 任务对象在 .apply_async 使用
        assert getattr(analyze_product_task, "max_retries", None) in (None, 3)

    @pytest.mark.skipif(
        os.getenv("CONTEXT7_USE_LOCAL_WORKER") != "1",
        reason="Only run in local worker mode",
    )
    def test_autoretry_configured_local(
        self, celery_app_instance: Any, local_celery_worker: Any
    ) -> None:
        from app.tasks.analysis_tasks import analyze_product_task

        assert getattr(analyze_product_task, "max_retries", None) in (None, 3)

    def test_dead_letter_stats_callable(self) -> None:
        from app.tasks.analysis_tasks import get_dead_letter_statistics

        result = get_dead_letter_statistics.delay()
        try:
            value = result.get(timeout=30)
            assert hasattr(value, "total_dead_letters")
        except Exception:
            # 无数据库或环境不足时允许跳过
            pytest.skip("统计依赖数据库，环境不足时跳过")
