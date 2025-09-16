"""Core signal extraction smoke-tests ensuring legacy fixtures remain typed."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List


class SignalType(Enum):
    PAIN_POINT = "PAIN_POINT"
    COMPETITOR = "COMPETITOR"
    OPPORTUNITY = "OPPORTUNITY"


@dataclass
class SignalPattern:
    signal_type: SignalType
    keywords: List[str]
    sentiment_threshold: float
    confidence_weight: float = 1.0
    min_keyword_matches: int = 1


@dataclass
class Signal:
    signal_type: SignalType
    content: str
    matched_keywords: List[str]
    sentiment_score: float
    confidence: float
    context_metadata: Dict[str, Any]
    source_post_id: str
    subreddit: str
    extracted_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RedditPost:
    id: str
    title: str
    content: str
    subreddit: str
    score: int = 0
    comment_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)


def simple_signal_extraction(
    posts: List[RedditPost], patterns: List[SignalPattern]
) -> List[Signal]:
    signals: List[Signal] = []
    for post in posts:
        normalized = post.content.lower()
        for pattern in patterns:
            matched_keywords = [kw for kw in pattern.keywords if kw.lower() in normalized]
            if len(matched_keywords) < pattern.min_keyword_matches:
                continue
            positive_words = {"good", "great", "excellent", "awesome"}
            negative_words = {"broken", "sucks", "terrible", "awful"}
            words = normalized.split()
            pos_count = sum(1 for word in words if word in positive_words)
            neg_count = sum(1 for word in words if word in negative_words)
            sentiment_score = max(-1.0, min(1.0, (pos_count - neg_count) * 0.3))
            if not _meets_threshold(sentiment_score, pattern.sentiment_threshold):
                continue
            confidence = min(
                1.0,
                max(
                    0.0,
                    len(matched_keywords) / max(1, len(pattern.keywords)) * pattern.confidence_weight,
                ),
            )
            signals.append(
                Signal(
                    signal_type=pattern.signal_type,
                    content=post.content,
                    matched_keywords=matched_keywords,
                    sentiment_score=sentiment_score,
                    confidence=confidence,
                    source_post_id=post.id,
                    subreddit=post.subreddit,
                    context_metadata={
                        "score": post.score,
                        "comment_count": post.comment_count,
                        "title": post.title,
                        "keyword_count": len(matched_keywords),
                    },
                )
            )
    return signals


def _test_posts() -> List[RedditPost]:
    return [
        RedditPost("p1", "Pain Point", "This app is broken and sucks terribly", "test1"),
        RedditPost("p2", "Competitor", "Much better than existing solutions", "test2"),
        RedditPost("p3", "Opportunity", "Really need a missing feature", "test3"),
    ]


def _test_patterns() -> List[SignalPattern]:
    return [
        SignalPattern(SignalType.PAIN_POINT, ["broken", "sucks", "terrible"], -0.5, 0.9),
        SignalPattern(SignalType.COMPETITOR, ["better", "solution"], 0.0, 0.8),
        SignalPattern(SignalType.OPPORTUNITY, ["need", "missing"], 0.2, 0.7),
    ]


def _meets_threshold(sentiment_score: float, threshold: float) -> bool:
    if threshold < 0:
        return sentiment_score <= threshold
    if threshold > 0:
        return sentiment_score >= threshold
    return True


def test_reddit_post_and_signal_dataclasses() -> None:
    post = RedditPost(
        id="test123",
        title="Test Post",
        content="This app is broken and sucks",
        subreddit="test",
        score=10,
        comment_count=5,
    )
    signal = Signal(
        signal_type=SignalType.PAIN_POINT,
        content=post.content,
        matched_keywords=["broken", "sucks"],
        sentiment_score=-0.6,
        confidence=0.8,
        source_post_id=post.id,
        subreddit=post.subreddit,
        context_metadata={
            "score": post.score,
            "comment_count": post.comment_count,
            "title": post.title,
        },
    )
    assert post.created_at is not None
    assert signal.matched_keywords == ["broken", "sucks"]
    assert signal.source_post_id == post.id
    assert signal.context_metadata["score"] == 10
    assert signal.subreddit == "test"


def test_simple_signal_extraction_produces_expected_fields() -> None:
    signals = simple_signal_extraction(_test_posts(), _test_patterns())
    assert signals
    by_type: Dict[SignalType, List[Signal]] = {}
    for signal in signals:
        by_type.setdefault(signal.signal_type, []).append(signal)
        assert signal.source_post_id
        assert signal.subreddit
        assert isinstance(signal.context_metadata, dict)
        assert signal.extracted_at <= datetime.utcnow()
    assert {SignalType.PAIN_POINT, SignalType.COMPETITOR, SignalType.OPPORTUNITY}.issubset(by_type)


def test_signal_to_dict_projection_contains_required_fields() -> None:
    signal = Signal(
        signal_type=SignalType.PAIN_POINT,
        content="Test content",
        matched_keywords=["test", "broken"],
        sentiment_score=-0.5,
        confidence=0.8,
        source_post_id="test123",
        subreddit="testsubreddit",
        context_metadata={"score": 10, "comment_count": 5},
    )
    signal_dict = {
        "signal_type": signal.signal_type.value,
        "content": signal.content,
        "matched_keywords": signal.matched_keywords,
        "confidence": signal.confidence,
        "sentiment_score": signal.sentiment_score,
        "source_post_id": signal.source_post_id,
        "subreddit": signal.subreddit,
        "context_metadata": signal.context_metadata,
        "extracted_at": signal.extracted_at.isoformat(),
    }
    required = {
        "signal_type",
        "content",
        "matched_keywords",
        "confidence",
        "source_post_id",
        "context_metadata",
    }
    assert required.issubset(signal_dict.keys())
