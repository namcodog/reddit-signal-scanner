"""
Algorithm Schemas Package

Type-safe algorithm response models to replace Dict[str, Any]
"""

from .community_ranking import (
    AlgorithmMetadataResponse,
    CommunityMetadataPydantic,
    PerformanceStatsResponse,
    RankingConfigPydantic,
    RankingResultPydantic,
    ScoreExplanationResponse,
    community_metadata_from_dataclass,
    ranking_result_from_dataclass,
)
from .opportunity_finder import (
    OpportunityAnalysisResponse,
    OpportunityFinderResponse,
    RedditPostListAdapter,
    RedditPostPydantic,
    SentimentTypePydantic,
    SignalListAdapter,
    SignalPatternPydantic,
    SignalPydantic,
    SignalTypePydantic,
    reddit_post_to_pydantic,
    signal_to_pydantic,
    signals_to_pydantic,
)

__all__ = [
    # Community Ranking Models
    "CommunityMetadataPydantic",
    "RankingConfigPydantic",
    "RankingResultPydantic",
    "PerformanceStatsResponse",
    "ScoreExplanationResponse",
    "AlgorithmMetadataResponse",
    "community_metadata_from_dataclass",
    "ranking_result_from_dataclass",
    # Opportunity Finder Models
    "SignalTypePydantic",
    "SentimentTypePydantic",
    "SignalPatternPydantic",
    "RedditPostPydantic",
    "SignalPydantic",
    "OpportunityFinderResponse",
    "OpportunityAnalysisResponse",
    "SignalListAdapter",
    "RedditPostListAdapter",
    "signals_to_pydantic",
    "signal_to_pydantic",
    "reddit_post_to_pydantic",
]
