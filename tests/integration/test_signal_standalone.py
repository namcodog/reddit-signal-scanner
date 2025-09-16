"""Standalone integration tests for simplified Reddit signal detection logic."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pytest


@dataclass
class SimpleSignalPattern:
    """Minimal pattern definition used by the simplified detector."""

    signal_type: str
    keywords: List[str]
    sentiment_threshold: float
    confidence_weight: float = 1.0
    min_keyword_matches: int = 1


@dataclass
class SimpleSignal:
    """Signal representation emitted by the simplified detector."""

    signal_type: str
    content: str
    confidence: float
    sentiment_score: float
    metadata: Dict[str, Any]


@dataclass
class SimpleRedditPost:
    """Reduced Reddit post model for standalone tests."""

    id: str
    content: str
    score: int
    subreddit: str
    comment_count: int


class SimpleRedditContextAdapter:
    """Handles small Reddit-specific text normalisation and sarcasm detection."""

    REDDIT_ABBREVIATIONS: Dict[str, str] = {
        "tbh": "to be honest",
        "imo": "in my opinion",
        "imho": "in my humble opinion",
        "fwiw": "for what it's worth",
        "tl;dr": "too long didn't read",
    }

    SARCASM_INDICATORS: List[str] = [
        "totally",
        "absolutely",
        "definitely",
        "clearly",
        "obviously",
        "/s",
        "not",
        "sure",
        "great job",
        "brilliant",
    ]

    def normalize_text(self, text: str) -> str:
        normalized = text.lower().strip()
        for abbr, full in self.REDDIT_ABBREVIATIONS.items():
            normalized = normalized.replace(abbr, full)
        return normalized.strip()

    def detect_sarcasm(self, text: str) -> bool:
        text_lower = text.lower()
        sarcasm_count = sum(1 for indicator in self.SARCASM_INDICATORS if indicator in text_lower)
        return sarcasm_count >= 2 or "/s" in text_lower


class SimpleSignalDetector:
    """Simplified implementation mirroring the production signal detector."""

    def __init__(self, patterns: List[SimpleSignalPattern]) -> None:
        self.patterns = patterns
        self.context_adapter = SimpleRedditContextAdapter()

    def extract_signals(self, reddit_posts: List[SimpleRedditPost]) -> List[SimpleSignal]:
        results: List[SimpleSignal] = []
        for post in reddit_posts:
            normalized_text = self.context_adapter.normalize_text(post.content)
            for pattern in self.patterns:
                signal = self._match_pattern(post, normalized_text, pattern)
                if signal is not None:
                    results.append(signal)
        return results

    def _match_pattern(
        self,
        post: SimpleRedditPost,
        normalized_text: str,
        pattern: SimpleSignalPattern,
    ) -> Optional[SimpleSignal]:
        keyword_matches = self._count_keyword_matches(normalized_text, pattern.keywords)
        if keyword_matches < pattern.min_keyword_matches:
            return None

        sentiment_score = self._simple_sentiment_analysis(normalized_text)
        if not self._meets_sentiment_threshold(sentiment_score, pattern.sentiment_threshold):
            return None

        confidence = self._calculate_confidence(keyword_matches, sentiment_score, pattern)
        if self.context_adapter.detect_sarcasm(post.content):
            confidence *= 0.7

        return SimpleSignal(
            signal_type=pattern.signal_type,
            content=(post.content[:200] + "...") if len(post.content) > 200 else post.content,
            confidence=min(1.0, max(0.0, confidence)),
            sentiment_score=sentiment_score,
            metadata={
                "post_id": post.id,
                "subreddit": post.subreddit,
                "score": post.score,
                "keyword_matches": keyword_matches,
            },
        )

    @staticmethod
    def _count_keyword_matches(text: str, keywords: List[str]) -> int:
        text_lower = text.lower()
        return sum(1 for keyword in keywords if keyword.lower() in text_lower)

    @staticmethod
    def _simple_sentiment_analysis(text: str) -> float:
        positive_words = {"good", "great", "excellent", "love", "awesome", "perfect", "amazing"}
        negative_words = {"bad", "terrible", "awful", "hate", "sucks", "broken", "frustrating"}
        words = text.lower().split()
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        total_words = len(words)
        if total_words == 0:
            return 0.0
        sentiment = (positive_count - negative_count) / total_words * 10
        return max(-1.0, min(1.0, sentiment))

    @staticmethod
    def _meets_sentiment_threshold(sentiment_score: float, threshold: float) -> bool:
        if threshold < 0:
            return sentiment_score <= threshold
        if threshold > 0:
            return sentiment_score >= threshold
        return abs(sentiment_score) <= 0.3

    @staticmethod
    def _calculate_confidence(
        keyword_matches: int,
        sentiment_score: float,
        pattern: SimpleSignalPattern,
    ) -> float:
        keyword_confidence = min(1.0, keyword_matches / max(1, len(pattern.keywords)))
        sentiment_confidence = 1.0 - abs(sentiment_score - pattern.sentiment_threshold) / 2.0
        sentiment_confidence = max(0.0, sentiment_confidence)
        confidence = (keyword_confidence * 0.7 + sentiment_confidence * 0.3) * pattern.confidence_weight
        return confidence


def _default_patterns() -> List[SimpleSignalPattern]:
    return [
        SimpleSignalPattern(
            signal_type="PAIN_POINT",
            keywords=["broken", "sucks", "terrible", "frustrating"],
            sentiment_threshold=-0.5,
            confidence_weight=0.9,
        ),
        SimpleSignalPattern(
            signal_type="COMPETITOR",
            keywords=["better than", "alternative", "compared to"],
            sentiment_threshold=0.0,
            confidence_weight=0.8,
        ),
        SimpleSignalPattern(
            signal_type="OPPORTUNITY",
            keywords=["need", "want", "missing", "lack"],
            sentiment_threshold=0.0,
            confidence_weight=0.7,
        ),
    ]


def _sample_posts() -> List[SimpleRedditPost]:
    return [
        SimpleRedditPost("1", "This app is broken and terrible, nothing works", 50, "productivity", 10),
        SimpleRedditPost("2", "Much better than Slack for team communication", 25, "tools", 5),
        SimpleRedditPost("3", "Really need a feature for batch processing, currently missing", 75, "requests", 15),
        SimpleRedditPost("4", "The interface sucks but has potential", 30, "ui", 8),
        SimpleRedditPost("5", "Perfect alternative to existing solutions", 60, "alternatives", 12),
    ]


def test_reddit_context_adapter_normalises_text() -> None:
    adapter = SimpleRedditContextAdapter()
    text = "tbh this sucks imo, totally broken"
    normalized = adapter.normalize_text(text)
    assert "to be honest" in normalized
    assert "in my opinion" in normalized
    assert adapter.detect_sarcasm("Great job breaking the app /s") is True
    assert adapter.detect_sarcasm("This is a good product") is False


def test_signal_detector_extracts_expected_types() -> None:
    detector = SimpleSignalDetector(_default_patterns())
    signals = detector.extract_signals(_sample_posts())
    assert signals, "Detector should emit at least one signal"
    grouped: Dict[str, List[SimpleSignal]] = {}
    for signal in signals:
        grouped.setdefault(signal.signal_type, []).append(signal)
        assert 0.0 <= signal.confidence <= 1.0
        assert -1.0 <= signal.sentiment_score <= 1.0
        assert isinstance(signal.metadata, dict)
    assert {"PAIN_POINT", "COMPETITOR", "OPPORTUNITY"}.issubset(grouped.keys())


def test_unified_processing_logic_handles_multiple_patterns() -> None:
    patterns = [
        SimpleSignalPattern("TYPE_A", ["keyword1", "keyword2"], -0.5),
        SimpleSignalPattern("TYPE_B", ["keyword3", "keyword4"], 0.0),
        SimpleSignalPattern("TYPE_C", ["keyword5", "keyword6"], 0.5),
    ]
    posts = [
        SimpleRedditPost("1", "This has keyword1 and is negative", 10, "test1", 1),
        SimpleRedditPost("2", "This has keyword3 and is neutral", 20, "test2", 2),
        SimpleRedditPost("3", "This has keyword5 and is positive", 30, "test3", 3),
    ]
    detector = SimpleSignalDetector(patterns)
    signals = detector.extract_signals(posts)
    signal_types = {signal.signal_type for signal in signals}
    assert signal_types == {"TYPE_A", "TYPE_B", "TYPE_C"}


def test_sarcasm_adjusts_confidence_downwards() -> None:
    detector = SimpleSignalDetector([SimpleSignalPattern("PAIN_POINT", ["broken"], -0.5, 1.0)])
    sarcastic_post = SimpleRedditPost("1", "This is totally broken /s", 10, "test", 1)
    regular_post = SimpleRedditPost("2", "This is totally broken", 10, "test", 1)
    signals = detector.extract_signals([sarcastic_post, regular_post])
    confidence_by_id = {signal.metadata["post_id"]: signal.confidence for signal in signals}
    assert confidence_by_id[sarcastic_post.id] < confidence_by_id[regular_post.id]


def test_detector_meets_performance_baseline() -> None:
    patterns = [
        SimpleSignalPattern("PAIN_POINT", ["broken", "terrible", "issues"], -0.5),
        SimpleSignalPattern("COMPETITOR", ["better than", "alternative"], 0.0),
        SimpleSignalPattern("OPPORTUNITY", ["need", "missing"], 0.2),
    ]
    detector = SimpleSignalDetector(patterns)
    content_templates = [
        "This product is broken and terrible",
        "Much better than the competition",
        "Really need this missing feature",
        "Great tool but has some issues",
        "Perfect alternative to existing solutions",
    ]
    dataset: List[SimpleRedditPost] = []
    for index in range(1000):
        content = f"{content_templates[index % len(content_templates)]} - post {index}"
        dataset.append(
            SimpleRedditPost(
                id=f"perf_test_{index}",
                content=content,
                score=index % 100,
                subreddit=f"test_{index % 10}",
                comment_count=index % 20,
            )
        )
    start = time.time()
    signals = detector.extract_signals(dataset)
    elapsed = time.time() - start
    assert elapsed < 60.0
    assert signals


@pytest.mark.asyncio
async def test_detector_can_be_used_in_async_context() -> None:
    """Small sanity check to ensure async wrappers can reuse the same detector."""
    detector = SimpleSignalDetector(_default_patterns())
    posts = _sample_posts()

    async def run_detection() -> List[SimpleSignal]:
        return detector.extract_signals(posts)

    result = await run_detection()
    assert result
