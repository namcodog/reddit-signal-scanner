"""
Ranking consistency and stability tests.

Verifies that the ResultRankingStep produces stable Top-K ordering under
minor weight perturbations.
"""

import pytest

from typing import Any, Dict

from backend.app.models.analysis_pipeline import PipelineData
from backend.app.services.analysis.result_ranker import process_ranking_step


def _make_pipeline_with_insights() -> PipelineData:
    pd = PipelineData(
        product_description="AI note tool",
        target_keywords=["ai", "note", "markdown"],
        analysis_config=None,
        pipeline_id="test",
        total_steps=4,
    )
    pd.step_results["signal_extraction"] = {
        "insights": {
            "pain_points": [
                {"description": "integration pain", "confidence": 0.8},
                {"description": "export issues", "confidence": 0.7},
            ],
            "competitors": [{"name": "comp-a"}],
            "opportunities": [
                {"description": "teams feature", "confidence": 0.6},
                {"description": "api marketplace", "confidence": 0.9},
            ],
        }
    }
    return pd


@pytest.mark.integration
def test_ranking_topk_stability_under_small_perturbation():
    data = _make_pipeline_with_insights()

    base_cfg: Dict[str, Any] = {"max_results": 3}
    r1 = process_ranking_step(data, base_cfg)
    assert r1.success
    top1 = tuple(r1.data.get("top_signals", []))

    # Slightly tweak internal weights (if consumed), keep Top-K stable
    perturbed_cfg: Dict[str, Any] = {"max_results": 3, "weight_bonus": 0.01}
    r2 = process_ranking_step(data, perturbed_cfg)
    assert r2.success
    top2 = tuple(r2.data.get("top_signals", []))

    # We only assert identity for the first K element set, allowing ordering ties
    assert set(top1) == set(top2)

