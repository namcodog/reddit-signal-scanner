from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.feedback_event import FeedbackEvent
from ...core.types import JsonValue, JsonDict
from typing import TypedDict


@dataclass(frozen=True)
class PatchWindow:
    start: datetime
    end: datetime


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def collect_community_decisions(
    session: AsyncSession,
    window: Optional[PatchWindow] = None,
) -> List[Dict[str, JsonValue]]:
    """收集指定时间窗口内的社区决策事件（community_decision）。"""
    if window is None:
        end = _now_utc()
        start = end - timedelta(days=1)
        window = PatchWindow(start=start, end=end)

    rows = (
        await session.execute(
            select(FeedbackEvent)
            .where(FeedbackEvent.event_type == "community_decision")
            .where(FeedbackEvent.created_at >= window.start)
            .where(FeedbackEvent.created_at <= window.end)
        )
    ).scalars().all()

    return [r.payload for r in rows]


def build_patch(decisions: List[Dict[str, JsonValue]]) -> PatchData:
    """根据社区决策事件构建 Patch 数据结构。"""
    core: List[str] = []
    experimental: List[str] = []
    blacklist: List[str] = []
    labels: Dict[str, List[str]] = {}

    for p in decisions:
        comm = str(p.get("community", "")).strip()
        if not comm:
            continue
        action = str(p.get("action", "")).strip()
        lab = p.get("labels", [])
        if isinstance(lab, list):
            labels[comm] = [str(x) for x in lab]

        if action == "approve":
            core.append(comm)
        elif action == "experiment":
            experimental.append(comm)
        elif action in {"pause", "blacklist"}:
            blacklist.append(comm)

    patch: PatchData = {
        "core": sorted(list(set(core))),
        "experimental": sorted(list(set(experimental))),
        "blacklist": sorted(list(set(blacklist))),
        "labels": labels,
        "_meta": {
            "generated_at": _now_utc().isoformat().replace("+00:00", "Z"),
            "total_events": len(decisions),
        },
    }
    return patch


def dump_yaml(patch: PatchData) -> str:
    """导出为YAML文本（稳定排序）。"""
    buf = io.StringIO()
    yaml.safe_dump(patch, buf, sort_keys=False, allow_unicode=True)
    return buf.getvalue()
class PatchData(TypedDict):
    core: List[str]
    experimental: List[str]
    blacklist: List[str]
    labels: Dict[str, List[str]]
    _meta: Dict[str, JsonValue]
