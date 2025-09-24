"""
Admin 反馈相关端点（骨架）

此模块提供：
- GET /admin/feedback/export  导出反馈原始事件（JSON/CSV）

数据来源（当前阶段）：
- 优先 Redis 列表键 rss:feedback:events（record_event 已写入）
- 失败时降级读取 backend/data/feedback_events.jsonl

权限：
- 需通过 JWT 认证，并具有 'admin' 或 'admin:read' 权限
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from ....core.database import get_session_factory
from ....core.redis_client import get_redis_client
from ....core.types import JsonValue
from ....api.deps.admin_guard import ensure_admin_read_access, ensure_admin_write_access
from ....schemas.admin.decisions import (AdminDecisionResponse,
                                         AdminDecisionSaved)
from ....schemas.feedback import (FeedbackEventRequest, FeedbackEventType,
                                  FeedbackSource, RatingValue)
from ....services.feedback_event_service import EVENT_LIST_KEY, FALLBACK_FILE
from ....services.feedback_event_store import create_event as db_create_event
from ....services.feedback_event_store import list_events as db_list_events

router = APIRouter(prefix="/admin/feedback", tags=["Admin-反馈"])


def _parse_iso(ts: str) -> Optional[datetime]:
    try:
        # 兼容末尾Z格式
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _load_from_jsonl(
    start_dt: Optional[datetime], end_dt: Optional[datetime], limit: int
) -> List[dict[str, JsonValue]]:
    items: List[dict[str, JsonValue]] = []
    if not FALLBACK_FILE.exists():
        return items
    try:
        with FALLBACK_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if _within_range(obj, start_dt, end_dt):
                    items.append(obj)
                    if len(items) >= limit:
                        break
    except Exception:
        # 读文件失败时返回已收集的数据
        pass
    return items


def _within_range(
    obj: dict[str, JsonValue], start_dt: Optional[datetime], end_dt: Optional[datetime]
) -> bool:
    ts = obj.get("timestamp")
    if not isinstance(ts, str):
        return False
    dt = _parse_iso(ts)
    if dt is None:
        return False
    if start_dt and dt < start_dt:
        return False
    if end_dt and dt > end_dt:
        return False
    return True


def _to_csv(rows: Iterable[dict[str, JsonValue]]) -> str:
    # 统一列头（缺失字段留空）
    headers = [
        "event_id",
        "timestamp",
        "request_id",
        "source",
        "event_type",
        "task_id",
        "analysis_id",
        "user_id",
        "rating",
        "reason",
        "comment",
        "insight_id",
        "flag",
        "tags",
        "metric_name",
        "metric_value",
        "metric_unit",
        "context",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers)
    writer.writeheader()
    for r in rows:
        row = dict(r)
        # 展平部分结构
        tags_value = row.get("tags")
        if isinstance(tags_value, list):
            row["tags"] = ",".join([str(x) for x in tags_value])
        if isinstance(row.get("context"), (dict, list)):
            row["context"] = json.dumps(row["context"], ensure_ascii=False)
        writer.writerow({k: row.get(k, "") for k in headers})
    return buf.getvalue()


@router.get("/export", summary="导出反馈原始事件（JSON/CSV）")
async def export_feedback_events(
    request: Request,
    start: Optional[str] = Query(default=None, description="起始时间（ISO8601）"),
    end: Optional[str] = Query(default=None, description="结束时间（ISO8601）"),
    format: str = Query(default="json", pattern="^(json|csv)$"),
    limit: int = Query(default=1000, ge=1, le=10000),
) -> Response:
    ensure_admin_read_access(request)

    start_dt = _parse_iso(start) if start else None
    end_dt = _parse_iso(end) if end else None

    # 1) 读取数据库（优先），2) Redis，3) JSONL 文件
    rows: List[dict[str, JsonValue]] = []
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            events = await db_list_events(
                session, start=start_dt, end=end_dt, limit=limit
            )
            rows = [e.payload for e in events]
    except Exception:
        try:
            client = await get_redis_client()
            raw_items = await client.lrange(EVENT_LIST_KEY, 0, limit - 1)
            for s in raw_items:
                obj = json.loads(s)
                if _within_range(obj, start_dt, end_dt):
                    rows.append(obj)
        except Exception:
            rows = _load_from_jsonl(start_dt, end_dt, limit)

    # 输出
    if format == "csv":
        csv_text = _to_csv(rows)
        fname = _build_filename("csv", start_dt, end_dt, len(rows))
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={fname}"},
        )
    else:
        return JSONResponse(
            content={
                "count": len(rows),
                "items": rows,
                "range": {"start": start, "end": end},
            }
        )


def _build_filename(
    ext: str, start_dt: Optional[datetime], end_dt: Optional[datetime], count: int
) -> str:
    def fmt(d: Optional[datetime]) -> str:
        return d.strftime("%Y%m%d-%H%M%S") if d else "auto"

    return f"feedback_events_{fmt(start_dt)}_{fmt(end_dt)}_{count}.{ext}"


# ====== PRD-07-06 算法反馈与汇总 ======


class AdminAnalysisFeedbackRequest(BaseModel):
    task_id: str = Field(..., description="任务ID")
    satisfied: bool = Field(..., description="是否满意")
    reasons: List[str] = Field(default_factory=list, description="原因枚举/自由文本")
    notes: Optional[str] = Field(default=None, description="备注")


class FeedbackSummaryData(BaseModel):
    window: Dict[str, Optional[str]]
    total: int
    likes: int
    dislikes: int
    top_reasons: List[Dict[str, Any]]


class FeedbackSummaryResponse(BaseModel):
    code: int = 0
    data: FeedbackSummaryData
    trace_id: Optional[str] = None


@router.post("/analysis", response_model=AdminDecisionResponse, summary="记录算法满意/不满意")
async def post_admin_analysis_feedback(
    request: Request, payload: AdminAnalysisFeedbackRequest
) -> AdminDecisionResponse:
    ensure_admin_write_access(request)

    session_factory = get_session_factory()
    async with session_factory() as session:
        ev_id = await db_create_event(
            session,
            FeedbackEventRequest(
                source=FeedbackSource.admin,
                event_type=FeedbackEventType.analysis_rating,
                task_id=payload.task_id,
                user_id=getattr(request.state, "user_id", None),
                rating=(RatingValue.like if payload.satisfied else RatingValue.dislike),
                reason=", ".join(payload.reasons) if payload.reasons else None,
                comment=payload.notes,
            ),
            request_id=getattr(request.state, "request_id", None),
        )
        await session.commit()

        return AdminDecisionResponse(
            code=0,
            data=AdminDecisionSaved(event_id=ev_id),
            trace_id=getattr(request.state, "request_id", None),
        )


@router.get("/summary", response_model=FeedbackSummaryResponse, summary="算法反馈汇总")
async def get_admin_feedback_summary(
    request: Request,
    days: int = Query(default=30, ge=1, le=90),
) -> FeedbackSummaryResponse:
    ensure_admin_read_access(request)

    session_factory = get_session_factory()
    start_dt = datetime.now(timezone.utc) - timedelta(days=days)
    async with session_factory() as session:
        from sqlalchemy import select

        from ....models.feedback_event import FeedbackEvent

        rows = (
            (
                await session.execute(
                    select(FeedbackEvent).where(
                        FeedbackEvent.created_at >= start_dt,
                        FeedbackEvent.event_type == "analysis_rating",
                    )
                )
            )
            .scalars()
            .all()
        )

        total = len(rows)
        likes = 0
        dislikes = 0
        reason_count: Dict[str, int] = {}
        for r in rows:
            p = r.payload
            rating = str(p.get("rating", ""))
            if rating == "like":
                likes += 1
            elif rating == "dislike":
                dislikes += 1
            reason = str(p.get("reason", "")).strip()
            if reason:
                # 可拆分多个原因，以逗号分隔
                for part in [x.strip() for x in reason.split(",") if x.strip()]:
                    reason_count[part] = reason_count.get(part, 0) + 1

        from typing import cast

        top_reasons_list = [{"reason": k, "count": v} for k, v in reason_count.items()]
        top_reasons = sorted(
            top_reasons_list,
            key=lambda x: cast(int, x["count"]),
            reverse=True,
        )[:10]

        return FeedbackSummaryResponse(
            code=0,
            data=FeedbackSummaryData(
                window={
                    "start": start_dt.isoformat().replace("+00:00", "Z"),
                    "end": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                },
                total=total,
                likes=likes,
                dislikes=dislikes,
                top_reasons=top_reasons,
            ),
            trace_id=getattr(request.state, "request_id", None),
        )
