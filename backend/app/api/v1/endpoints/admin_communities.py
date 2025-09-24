from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query, Request, HTTPException

from ....api.deps.admin_guard import ensure_admin_read_access, ensure_admin_write_access
from ....core.database import get_session_factory
from ....models.community_cache import CommunityCache
from ....models.analysis import Analysis
from ....services.community_metrics import ExternalStats, assemble_summary
from ....schemas.admin.community import (
    CommunitySummary,
    CommunitiesListResponse,
    CommunitiesListData,
)
from ....schemas.admin.decisions import (
    AdminCommunityDecisionRequest,
    AdminDecisionResponse,
    AdminDecisionSaved,
)
from ....schemas.feedback import FeedbackEventRequest, FeedbackEventType, FeedbackSource
from sqlalchemy.ext.asyncio import AsyncSession
from ....services.feedback_event_store import create_event as db_create_event


router = APIRouter(prefix="/admin/communities", tags=["Admin-社区"])


def _default_stats_from_cache(row: CommunityCache) -> ExternalStats:
    # 简化提供器：用命中次数近似 hit_7d，并给出温和默认 dup/spam
    hit_7d = min(50, int(row.hit_count))
    topic = float(row.quality_score) if hasattr(row, "quality_score") else 0.6
    return ExternalStats(
        hit_7d=hit_7d,
        dup_ratio=0.08,
        spam_ratio=0.07,
        topic_score=min(1.0, max(0.0, topic)),
        evidence_samples=[],
    )


@router.get("/summary", response_model=CommunitiesListResponse)
async def get_communities_summary(
    request: Request,
    q: Optional[str] = Query(default=None, description="按社区名模糊搜索"),
    status: Optional[str] = Query(default=None, pattern="^(green|yellow|red)$"),
    sort: str = Query(default="cscore_desc", pattern="^(cscore_desc|hit_desc)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> CommunitiesListResponse:
    ensure_admin_read_access(request)

    session_factory = get_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select, text, bindparam
        from datetime import datetime, timedelta, timezone

        # 预聚合：近7天 Analysis → community 命中数与平均置信度
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        analysis_rows = (
            await session.execute(
                select(Analysis.sources, Analysis.confidence_score, Analysis.created_at).where(
                    Analysis.created_at >= seven_days_ago
                )
            )
        ).all()
        hits: dict[str, int] = {}
        conf_sum: dict[str, float] = {}
        for src, conf, _created in analysis_rows:
            try:
                comms = list(src.get("communities", [])) if isinstance(src, dict) else []
            except Exception:
                comms = []
            for name in comms:
                if not isinstance(name, str):
                    continue
                hits[name] = hits.get(name, 0) + 1
                try:
                    conf_f = float(conf)
                except Exception:
                    conf_f = 0.6
                conf_sum[name] = conf_sum.get(name, 0.0) + conf_f

        # 读取真实 dup/spam 来源视图（若存在），一次性批量查询
        quality_map: dict[str, tuple[float, float]] = {}
        try:
            # 预先获取所有可能用到的社区名（稍后还要再取 rows 列表，重复一次也可接受）
            name_candidates = list(hits.keys())
            if name_candidates:
                q_stmt = text(
                    "SELECT community, dup_ratio, spam_ratio "
                    "FROM vw_community_quality WHERE community IN :names"
                ).bindparams(bindparam("names", expanding=True))
                res = await session.execute(q_stmt, {"names": name_candidates})
                for community, dup_v, spam_v in res.fetchall():
                    try:
                        d = max(0.0, min(1.0, float(dup_v)))
                        s = max(0.0, min(1.0, float(spam_v)))
                        quality_map[str(community)] = (d, s)
                    except Exception:
                        continue
        except Exception:
            quality_map = {}

        def provider_from_map(cc: CommunityCache) -> ExternalStats:
            name = cc.community_name
            h = hits.get(name, 0)
            avg_conf = (conf_sum.get(name, 0.0) / h) if h > 0 else float(getattr(cc, "quality_score", 0.6))
            dup_v, spam_v = quality_map.get(name, (0.08, 0.07))
            return ExternalStats(
                hit_7d=h,
                dup_ratio=dup_v,
                spam_ratio=spam_v,
                topic_score=max(0.0, min(1.0, avg_conf)),
                evidence_samples=[],
            )

        stmt = select(CommunityCache)
        if q:
            stmt = stmt.where(CommunityCache.community_name.ilike(f"%{q}%"))
        # 为了正确计算 status 过滤下的 total，先不分页，汇总后再切片
        rows = (await session.execute(stmt)).scalars().all()

        # 视图中缺失的社区再补查一次
        all_row_names = [cc.community_name for cc in rows]
        missing = [n for n in all_row_names if n not in quality_map]
        if missing:
            try:
                q_stmt2 = text(
                    "SELECT community, dup_ratio, spam_ratio FROM vw_community_quality WHERE community IN :names"
                ).bindparams(bindparam("names", expanding=True))
                res2 = await session.execute(q_stmt2, {"names": missing})
                for community, dup_v, spam_v in res2.fetchall():
                    try:
                        d = max(0.0, min(1.0, float(dup_v)))
                        s = max(0.0, min(1.0, float(spam_v)))
                        quality_map[str(community)] = (d, s)
                    except Exception:
                        continue
            except Exception:
                pass

        summaries: List[CommunitySummary] = []
        for cc in rows:
            stats = provider_from_map(cc)
            summaries.append(assemble_summary(cc, stats))

        if status:
            summaries = [s for s in summaries if s.status_color == status]

        if sort == "cscore_desc":
            summaries.sort(key=lambda s: s.c_score, reverse=True)
        else:
            summaries.sort(key=lambda s: s.hit_7d, reverse=True)
        total = len(summaries)
        sliced = summaries[offset : offset + limit]

        return CommunitiesListResponse(
            code=0,
            data=CommunitiesListData(items=sliced, total=total),
            trace_id=getattr(request.state, "request_id", None),
        )


async def await_single(session: AsyncSession, community_name: str) -> Optional[CommunityCache]:
    row = await session.get(CommunityCache, community_name)
    return row


@router.post("/decisions/community", response_model=AdminDecisionResponse)
async def post_community_decision(
    request: Request, payload: AdminCommunityDecisionRequest
) -> AdminDecisionResponse:
    ensure_admin_write_access(request)

    session_factory = get_session_factory()
    async with session_factory() as session:
        # 写入 feedback_events（community_decision）
        ev_id = await db_create_event(
            session,
            FeedbackEventRequest(
                source=FeedbackSource.admin,
                event_type=FeedbackEventType.community_decision,
                task_id="",
                user_id=getattr(request.state, "user_id", None),
                context={
                    "community": payload.community,
                    "action": payload.action,
                    "labels": payload.labels,
                    "reason": payload.reason,
                },
            ),
            request_id=getattr(request.state, "request_id", None),
        )
        await session.commit()

        return AdminDecisionResponse(
            code=0,
            data=AdminDecisionSaved(event_id=ev_id),
            trace_id=getattr(request.state, "request_id", None),
        )
