import asyncio
import time
from typing import Any, Dict, List

import pytest

from backend.app.services.analysis_engine import AnalysisEngine
from backend.app.models.analysis_pipeline import PipelineResult, StepStatus
from backend.app.models.signal_pattern import RedditPost as SPRedditPost


pytestmark = pytest.mark.integration


def _fake_communities(n: int = 5) -> List[Dict[str, Any]]:
    return [
        {
            "name": f"r/test{i}",
            "relevance_score": {"final_score": 0.5 + (i * 0.05)},
            "member_count": 10000 + i,
        }
        for i in range(n)
    ]


def _fake_reddit_posts() -> List[SPRedditPost]:
    # Construct minimal posts for downstream steps when needed
    return [
        SPRedditPost(
            id="p1",
            title="This app sucks",
            content="complaint negative_experience the app is broken and frustrating",
            subreddit="r/test1",
            score=120,
            comment_count=15,
        ),
        SPRedditPost(
            id="p2",
            title="X is better than Y",
            content="neutral comparison brand_mention X is better than Y for task",
            subreddit="r/test2",
            score=80,
            comment_count=8,
        ),
        SPRedditPost(
            id="p3",
            title="I would pay for this",
            content=(
                "feature_request unmet_need wish there was a simple tool, I would pay for it"
            ),
            subreddit="r/test3",
            score=60,
            comment_count=6,
        ),
    ]


@pytest.mark.asyncio
async def test_analysis_engine_pipeline_runs_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = AnalysisEngine()

    # Monkeypatch Step 1: community_discovery
    async def _step1(_self, data):  # type: ignore[no-redef]
        return PipelineResult(
            step_name="communitydiscovery",
            duration=0.01,
            data={
                "communities": _fake_communities(5),
                "total_found": 5,
                "algorithm_metadata": {"extracted_info": {"confidence": 0.8}},
                "processing_stats": {"took_ms": 10},
                "confidence_score": 0.75,
                "recommendations": [],
            },
            success=True,
            status=StepStatus.COMPLETED,
        )

    # Monkeypatch Step 2: data_collection → provide reddit_posts for signal extraction
    async def _step2(_self, data):  # type: ignore[no-redef]
        posts = _fake_reddit_posts()
        return PipelineResult(
            step_name="datacollection",
            duration=0.01,
            data={
                "reddit_posts": posts,
                "cache_hit_rate": 0.9,
                "api_calls": 2,
                "total_posts": len(posts),
            },
            success=True,
            status=StepStatus.COMPLETED,
        )

    # Monkeypatch Step 3: signal_extraction → return insights mapping for ranking
    async def _step3(_self, data):  # type: ignore[no-redef]
        now = time.time()
        return PipelineResult(
            step_name="signal_extraction",
            duration=0.02,
            data={
                "insights": {
                    "pain_points": [
                        {
                            "id": "pp1",
                            "title": "App is broken",
                            "content": "complaint about broken app",
                            "relevance_score": 0.7,
                            "timestamp": now,
                        }
                    ],
                    "opportunities": [
                        {
                            "id": "op1",
                            "title": "Would pay for X",
                            "content": "feature_request unmet_need",
                            "relevance_score": 0.8,
                            "timestamp": now,
                        }
                    ],
                    "competitors": [
                        {
                            "id": "cp1",
                            "title": "X vs Y",
                            "content": "comparison brand_mention",
                            "relevance_score": 0.6,
                            "timestamp": now,
                        }
                    ],
                    "analysis_summary": "mock summary",
                    "confidence_score": 0.7,
                }
            },
            success=True,
            status=StepStatus.COMPLETED,
        )

    # Attach monkeypatches to the step instances
    # Order: [CommunityDiscoveryStep, DataCollectionStep, SignalExtractionStep, ResultRankingStep]
    assert len(engine.steps) == 4
    # Patch on the classes so methods bind correctly
    monkeypatch.setattr(engine.steps[0].__class__, "_process_step", _step1)
    monkeypatch.setattr(engine.steps[1].__class__, "_process_step", _step2)
    monkeypatch.setattr(engine.steps[2].__class__, "_process_step", _step3)

    # Execute the analysis
    report = await engine.analyze(
        product_description="Awesome mobile app for productivity on Reddit",
        target_keywords=["productivity", "mobile", "reddit"],
        max_communities=5,
        include_raw_data=False,
    )

    # Validations
    assert report.total_duration >= 0.0
    # At least community discovery and data collection executed
    assert len(report.step_durations) >= 2

    # Confidence is computed; ensure it is a valid ratio [0,1]
    assert 0.0 <= report.confidence_score <= 1.0

    # Executive summary exists and contains keys
    summary = report.get_executive_summary()
    assert "总洞察数" in summary
    assert "置信度" in summary
    assert "分析时长" in summary

    # Actionability heuristic (may still be False depending on step durations)
    assert isinstance(report.is_actionable(), bool)
