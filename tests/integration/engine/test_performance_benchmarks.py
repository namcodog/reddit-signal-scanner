"""
Lightweight performance envelope checks (no external services).

We simulate durations via PipelineData to validate 5-minute SLA and per-step accounting.
"""

from backend.app.models.analysis_pipeline import AnalysisConfig, PipelineData
from backend.app.services.analysis_engine import AnalysisEngine

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_total_duration_under_sla() -> None:
    engine = AnalysisEngine()
    pipeline = PipelineData(
        product_description="perf-test",
        analysis_config=AnalysisConfig(product_description="perf-test"),
        pipeline_id="perf",
        total_steps=4,
    )
    pipeline.step_durations = [10.0, 20.0, 15.0, 5.0]

    report = await engine._build_analysis_report(pipeline)
    assert report.total_duration < 300.0
    assert sum(pipeline.step_durations) == report.total_duration
