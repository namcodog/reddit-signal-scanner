"""
Lightweight performance envelope checks (no external services).

We simulate durations via PipelineData to validate 5-minute SLA and per-step accounting.
"""

import pytest

from backend.app.services.analysis_engine import AnalysisEngine
from backend.app.models.analysis_pipeline import PipelineData


@pytest.mark.integration
@pytest.mark.asyncio
async def test_total_duration_under_sla():
    engine = AnalysisEngine()
    pd = engine._create_pipeline_data("perf-test",  # type: ignore[arg-type]
                                      config=type("Cfg", (), {  # minimal cfg stub
                                          "product_description": "X",
                                          "target_keywords": [],
                                          "max_communities": 5,
                                          "enable_cache": True,
                                          "priority": "normal",
                                          "output_format": "structured",
                                          "include_raw_data": False,
                                          "max_total_time": 60.0,
                                      })())
    # Simulate durations for 4 steps totalling well below 300s
    pd.step_durations = [10.0, 20.0, 15.0, 5.0]

    report = await engine._build_analysis_report(pd)  # type: ignore[attr-defined]
    assert report.total_duration < 300.0
    assert sum(pd.step_durations) == report.total_duration

