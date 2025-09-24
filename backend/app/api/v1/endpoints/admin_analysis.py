from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Path, Query, Request, HTTPException

from ....api.deps.admin_guard import ensure_admin_read_access
from ....core.database import get_session_factory
from ....models.task import Task
from ....services.analysis_metrics import (
    ExternalAnalysisMetrics,
    summarize_task,
)
from ....schemas.admin.analysis import (
    AnalysisSummary,
    AnalysisMustGates,
    AnalysisListResponse,
    AnalysisListData,
)


router = APIRouter(prefix="/admin/analysis", tags=["Admin-算法验收"])


def _default_metrics() -> ExternalAnalysisMetrics:
    return ExternalAnalysisMetrics(
        coverage=0.72,
        relevance=0.78,
        evidence_per_insight_avg=1.2,
        median_days=3.0,
        dup_ratio=0.10,
        spam_ratio=0.06,
        diversity=0.60,
        safety_pass=True,
    )


@router.get("/summary", response_model=AnalysisListResponse)
async def get_analysis_summary(
    request: Request,
    q: Optional[str] = Query(default=None, description="按 task_id 模糊搜索"),
    sort: str = Query(default="ascore_desc", pattern="^(ascore_desc|fresh_asc)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> AnalysisListResponse:
    # 权限检查（读）
    ensure_admin_read_access(request)

    session_factory = get_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select, desc

        stmt = select(Task.id).order_by(desc(Task.created_at))
        rows = (await session.execute(stmt)).scalars().all()

        summaries: List[AnalysisSummary] = []
        for tid in rows:
            s = summarize_task(str(tid), _default_metrics(), gates=AnalysisMustGates())
            summaries.append(s)

        if q:
            summaries = [s for s in summaries if q in s.task_id]

        if sort == "ascore_desc":
            summaries.sort(key=lambda s: s.a_score, reverse=True)
        else:
            summaries.sort(key=lambda s: s.median_days)

        total = len(summaries)
        sliced = summaries[offset : offset + limit]

        # 复用 CommunitiesListResponse 包装结构（code/data/items/total/trace_id）
        return AnalysisListResponse(
            code=0,
            data=AnalysisListData(items=sliced, total=total),
            trace_id=getattr(request.state, "request_id", None),
        )


@router.get("/{task_id}", response_model=AnalysisSummary)
async def get_analysis_detail(
    request: Request, task_id: str = Path(..., description="任务ID(UUID)")
) -> AnalysisSummary:
    ensure_admin_read_access(request)

    # 校验任务存在
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            tid_uuid = UUID(task_id)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid task_id")

        row = await session.get(Task, tid_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="task not found")

        return summarize_task(task_id, _default_metrics(), gates=AnalysisMustGates())
