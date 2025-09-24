from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.community_cache import CommunityCache
from app.services.community_metrics import ExternalStats, assemble_summary, summarize_communities


@pytest.mark.asyncio
async def test_assemble_summary_basic(db_session: "object") -> None:
    now = datetime.now(timezone.utc)
    # 构造一条社区数据：24小时内抓取，命中等
    cc = CommunityCache(
        community_name="r/startups",
        last_crawled_at=now - timedelta(hours=24),
        ttl_seconds=3600,
        posts_cached=100,
        quality_score=Decimal("0.80"),
        hit_count=123,
        last_hit_at=now - timedelta(hours=1),
        crawl_priority=10,
    )
    db_session.add(cc)
    await db_session.commit()

    stats = ExternalStats(
        hit_7d=40,
        dup_ratio=0.1,
        spam_ratio=0.05,
        topic_score=0.75,
        evidence_samples=["https://reddit.com/...1", "https://reddit.com/...2"],
    )

    summary = assemble_summary(cc, stats, now=now)

    # Must Gates 应当全部通过
    assert summary.must.freshness_ok is True
    assert summary.must.hits_ok is True
    assert summary.must.dup_ok is True
    assert summary.must.spam_ok is True
    assert summary.must.topic_ok is True

    # C-Score 范围与颜色
    assert 70 <= summary.c_score <= 100
    assert summary.status_color == "green"
    assert summary.community == "r/startups"
    assert summary.hit_7d == 40
    assert len(summary.evidence_samples) == 2


@pytest.mark.asyncio
async def test_summarize_communities_with_provider(db_session: "object") -> None:
    now = datetime.now(timezone.utc)
    # 插入两条社区
    for name in ("r/a", "r/b"):
        db_session.add(
            CommunityCache(
                community_name=name,
                last_crawled_at=now - timedelta(hours=12),
                ttl_seconds=3600,
                posts_cached=50,
                quality_score=Decimal("0.70"),
                hit_count=10,
                last_hit_at=now - timedelta(hours=2),
                crawl_priority=20,
            )
        )
    await db_session.commit()

    def provider(comm: str) -> ExternalStats:
        base = 35 if comm == "r/a" else 10
        return ExternalStats(
            hit_7d=base,
            dup_ratio=0.08,
            spam_ratio=0.07,
            topic_score=0.65,
            evidence_samples=[],
        )

    res = await summarize_communities(db_session, provider, limit=10)
    assert len(res) == 2
    # r/a 应接近通过，r/b hits 不达标 → 颜色至少不是 green
    m = {x.community: x for x in res}
    assert m["r/a"].must.hits_ok is True
    assert m["r/b"].must.hits_ok is False
