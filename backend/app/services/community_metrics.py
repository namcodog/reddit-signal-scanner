"""
社区指标计算服务（PRD‑07‑02）

职责：
- 基于 CommunityCache + 外部聚合指标 计算 Must Gates 与 C‑Score
- 输出 Admin 社区页需要的 CommunitySummary

注意：
- 外部指标（hit_7d/dup/spam/topic/evidence）由上层聚合器提供，此处只做纯计算与装配
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, List, Optional, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.community_cache import CommunityCache
from ..schemas.admin.community import (
    CommunitySummary,
    MustGates,
    MustResult,
)
from typing import cast


@dataclass(frozen=True)
class ExternalStats:
    hit_7d: int
    dup_ratio: float
    spam_ratio: float
    topic_score: float  # 0~1
    evidence_samples: List[str]


def _hours_since(ts: Optional[datetime], now: datetime) -> float:
    if ts is None:
        return 1e9  # 极大值，表示从未抓取
    # 统一用UTC比较
    base = ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    return max(0.0, (now - base).total_seconds() / 3600.0)


def _compute_scores(hit_7d: int, freshness_h: float, topic_score: float, dup_ratio: float, spam_ratio: float) -> tuple[float, float, float, int]:
    # activity: 命中越多越活跃，上限1.0
    activity = min(hit_7d / 50.0, 1.0) * 100.0
    # freshness: 小于等于48小时满分
    freshness = max(0.0, 1.0 - freshness_h / 48.0) * 100.0
    topic_percent = max(0.0, min(1.0, topic_score)) * 100.0

    c = 0.35 * topic_percent + 0.25 * activity + 0.20 * freshness + 0.10 * ((1.0 - spam_ratio) * 100.0) + 0.10 * ((1.0 - dup_ratio) * 100.0)
    return activity, freshness, topic_percent, int(round(max(0.0, min(100.0, c))))


def _must_check(g: MustGates, freshness_h: float, hit_7d: int, dup_ratio: float, spam_ratio: float, topic_score: float) -> MustResult:
    return MustResult(
        freshness_ok=freshness_h <= g.freshness_hours_max,
        hits_ok=hit_7d >= g.min_hits_7d,
        dup_ok=dup_ratio <= g.max_dup_ratio,
        spam_ok=spam_ratio <= g.max_spam_ratio,
        topic_ok=topic_score >= g.min_topic_score,
    )


def _status_color(c_score: int, must: MustResult) -> str:
    if not must.all_passed():
        return "red"
    if c_score >= 70:
        return "green"
    if c_score >= 55:
        return "yellow"
    return "red"


def assemble_summary(
    community: CommunityCache,
    stats: ExternalStats,
    now: Optional[datetime] = None,
    gates: Optional[MustGates] = None,
) -> CommunitySummary:
    now_dt = now or datetime.now(timezone.utc)
    g = gates or MustGates()

    freshness_h = _hours_since(community.last_crawled_at, now_dt)
    activity, freshness, topic_percent, c = _compute_scores(
        hit_7d=stats.hit_7d,
        freshness_h=freshness_h,
        topic_score=stats.topic_score,
        dup_ratio=stats.dup_ratio,
        spam_ratio=stats.spam_ratio,
    )
    must = _must_check(g, freshness_h, stats.hit_7d, stats.dup_ratio, stats.spam_ratio, stats.topic_score)
    color = _status_color(c, must)

    return CommunitySummary(
        community=community.community_name,
        last_crawled_at=community.last_crawled_at,
        freshness_hours=freshness_h,
        hit_7d=stats.hit_7d,
        dup_ratio=stats.dup_ratio,
        spam_ratio=stats.spam_ratio,
        topic_score=stats.topic_score,
        activity_score=activity,
        freshness_score=freshness,
        topic_percent=topic_percent,
        c_score=c,
        status_color=cast(Literal["green","yellow","red"], color),
        must=must,
        evidence_samples=list(stats.evidence_samples),
    )


async def summarize_communities(
    session: AsyncSession,
    provider: Callable[[str], ExternalStats],
    limit: int = 100,
) -> List[CommunitySummary]:
    """列出社区汇总信息。

    Args:
        session: AsyncSession
        provider: 根据社区名提供外部统计指标的回调
        limit: 返回数量上限
    """
    rows = (await session.execute(select(CommunityCache).limit(limit))).scalars().all()
    out: List[CommunitySummary] = []
    for row in rows:
        stats = provider(row.community_name)
        out.append(assemble_summary(row, stats))
    return out
