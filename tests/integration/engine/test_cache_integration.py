from typing import Any

import pytest

from backend.app.services.data_collector import (
    CollectionConfig,
    DataCollectionService,
)
from backend.app.core.redis_client import CacheKeys


pytestmark = pytest.mark.integration


def _mk_cfg() -> CollectionConfig:
    return CollectionConfig(target_communities=["r/test1", "r/test2", "r/test3"], max_api_calls=15)


def test_strategy_selection_by_cache_hit_rate() -> None:
    svc = DataCollectionService()
    cfg = _mk_cfg()

    # High hit rate → cache_dominant, <=5 api calls
    s1 = svc._determine_collection_strategy({"hit_rate": 0.85}, cfg)
    assert s1["name"] == "cache_dominant"
    assert s1["max_api_calls"] <= 5

    # Medium hit rate → hybrid, <=10 api calls
    s2 = svc._determine_collection_strategy({"hit_rate": 0.65}, cfg)
    assert s2["name"] == "hybrid"
    assert s2["max_api_calls"] <= 10

    # Low hit rate → api_heavy, =max_api_calls
    s3 = svc._determine_collection_strategy({"hit_rate": 0.2}, cfg)
    assert s3["name"] == "api_heavy"
    assert s3["max_api_calls"] == cfg.max_api_calls


def test_cache_key_generation_patterns() -> None:
    # Ensures Redis key naming is stable (contract)
    assert CacheKeys.reddit_task_data("abc") == "rss:reddit:task_data:abc"
    assert CacheKeys.reddit_api_response("hot", "p123") == "rss:reddit:api:hot:p123"
    assert CacheKeys.analysis_result("aid") == "rss:analysis:result:aid"
    assert CacheKeys.user_session("u1") == "rss:session:user:u1"
    assert CacheKeys.api_rate_limit("127.0.0.1", "/v1/x") == "rss:rate_limit:127.0.0.1:/v1/x"

