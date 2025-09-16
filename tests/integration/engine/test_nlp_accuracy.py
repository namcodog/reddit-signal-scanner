from typing import Any, List, cast

import pytest

from backend.app.models.analysis_pipeline import AnalysisConfig, PipelineData
from backend.app.services.analysis.signal_extractor import RedditSignalExtractor
from backend.app.models.signal_pattern import RedditPost as SPRedditPost


pytestmark = pytest.mark.integration


def _posts_for_accuracy() -> List[SPRedditPost]:
    return [
        # Pain point (negative sentiment + context rule)
        SPRedditPost(
            id="a1",
            title="This tool is awful",
            content="complaint negative_experience totally broken and sucks",
            subreddit="r/tools",
            score=50,
            comment_count=7,
        ),
        # Competitor (neutral + comparison)
        SPRedditPost(
            id="a2",
            title="Is A better than B?",
            content="comparison brand_mention What's better than brand B for this?",
            subreddit="r/compare",
            score=30,
            comment_count=3,
        ),
        # Opportunity (positive + feature request)
        SPRedditPost(
            id="a3",
            title="I would pay for automation, amazing idea",
            content=(
                "feature_request unmet_need wish there was a simple automation tool, great and amazing"
            ),
            subreddit="r/ideas",
            score=40,
            comment_count=4,
        ),
    ]


@pytest.mark.asyncio
async def test_signal_extraction_detects_three_signal_types() -> None:
    extractor = RedditSignalExtractor()

    data = PipelineData(
        product_description="Test product for Reddit analysis",
        analysis_config=AnalysisConfig(product_description="Test product for Reddit analysis"),
    )

    # Provide reddit_posts as DataCollection output for the extractor
    data.step_results["data_collection"] = cast(
        dict[str, Any],
        {"reddit_posts": _posts_for_accuracy()},
    )

    result = await extractor.process(data)

    assert result.success is True
    stats = result.data.get("statistics", {})
    assert isinstance(stats, dict)

    # Expect at least one of each
    assert stats.get("pain_point", 0) >= 1
    assert stats.get("competitor", 0) >= 1
    assert stats.get("opportunity", 0) >= 1

    # Basic quality metric presence
    quality = result.data.get("quality_metrics", {})
    assert isinstance(quality, dict)
    assert "extraction_rate" in quality
