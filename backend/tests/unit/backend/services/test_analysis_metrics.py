from __future__ import annotations

import pytest

from app.services.analysis_metrics import (
    ExternalAnalysisMetrics,
    summarize_task,
)


@pytest.mark.parametrize(
    "m,expect_green",
    [
        (
            ExternalAnalysisMetrics(
                coverage=0.85,
                relevance=0.80,
                evidence_per_insight_avg=1.5,
                median_days=3.0,
                dup_ratio=0.10,
                spam_ratio=0.05,
                diversity=0.60,
                safety_pass=True,
            ),
            True,
        ),
        (
            ExternalAnalysisMetrics(
                coverage=0.60,
                relevance=0.65,
                evidence_per_insight_avg=0.8,
                median_days=10.0,
                dup_ratio=0.20,
                spam_ratio=0.12,
                diversity=0.30,
                safety_pass=True,
            ),
            False,
        ),
    ],
)
def test_summarize_task_must_and_a_score(m: ExternalAnalysisMetrics, expect_green: bool) -> None:
    s = summarize_task("task_x", m)
    if expect_green:
        assert s.must.all_passed() is True
        assert s.a_score >= 75
    else:
        assert s.must.all_passed() is False
        assert s.a_score <= 75
