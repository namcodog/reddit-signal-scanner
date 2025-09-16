"""Integration tests for the Reddit signal extractor with strict typing expectations."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, cast

import pytest

from backend.app.models.analysis_pipeline import (
    AnalysisConfig,
    PipelineData,
    StepResultValue,
)
from backend.app.models.signal_pattern import (
    DEFAULT_SIGNAL_PATTERNS,
    RedditPost,
    Signal,
    SignalType,
)
from backend.app.services.analysis.signal_extractor import (
    RedditSignalExtractor,
    UnifiedSignalDetector,
)


def _create_post(
    post_id: str,
    title: str,
    content: str,
    subreddit: str = "test",
) -> RedditPost:
    """Build a minimal RedditPost instance used in integration tests."""
    return RedditPost(
        id=post_id,
        title=title,
        content=content,
        subreddit=subreddit,
        score=10,
        comment_count=5,
        created_at=datetime.utcnow(),
    )


def test_detector_extracts_signals_from_posts() -> None:
    posts: List[RedditPost] = [
        _create_post("post1", "Pain Point", "This app is broken and frustrating"),
        _create_post("post2", "Competitor", "Better than Slack for team collaboration"),
        _create_post("post3", "Opportunity", "Need a batch processing feature urgently"),
    ]

    detector = UnifiedSignalDetector(DEFAULT_SIGNAL_PATTERNS)
    signals = detector.extract_signals(posts)

    assert signals, "Expected at least one signal to be extracted"
    for signal in signals:
        assert isinstance(signal, Signal)
        assert isinstance(signal.signal_type, SignalType)
        assert signal.source_post_id in {post.id for post in posts}
        assert signal.matched_keywords, "Matched keywords should not be empty"
        assert isinstance(signal.context_metadata, dict)


@pytest.mark.asyncio
async def test_signal_extractor_step_executes_with_pipeline_data() -> None:
    config = AnalysisConfig(product_description="Test product for signal extraction")
    pipeline = PipelineData(
        product_description=config.product_description,
        target_keywords=["test"],
        analysis_config=config,
        pipeline_id="test-pipeline",
        total_steps=4,
    )

    collected_posts: List[RedditPost] = [
        _create_post("integration1", "Integration Test", "This tool is broken and frustrating"),
        _create_post("integration2", "Competitor Test", "Better than existing solutions"),
    ]

    pipeline.step_results["data_collection"] = cast(
        Dict[str, StepResultValue],
        {
            "reddit_posts": collected_posts,
            "total_posts": len(collected_posts),
        },
    )

    extractor = RedditSignalExtractor()
    result = await extractor.execute(pipeline)

    assert result.success is True
    signals_json = result.data.get("signals")
    assert isinstance(signals_json, list)
    assert signals_json, "Signal extractor should return at least one signal entry"

    first_signal = signals_json[0]
    assert isinstance(first_signal, dict)
    for field in ("signal_type", "matched_keywords", "source_post_id", "context_metadata"):
        assert field in first_signal


def test_data_model_instances_are_valid() -> None:
    post = _create_post("compat1", "Compatibility Test", "Test content")
    assert post.id == "compat1"

    signal = Signal(
        signal_type=SignalType.PAIN_POINT,
        content="Test signal content",
        matched_keywords=["test", "broken"],
        sentiment_score=-0.5,
        confidence=0.8,
        source_post_id=post.id,
        subreddit=post.subreddit,
    )

    assert signal.signal_type is SignalType.PAIN_POINT
    assert signal.matched_keywords == ["test", "broken"]
    assert signal.source_post_id == post.id
    assert signal.context_metadata == {}
