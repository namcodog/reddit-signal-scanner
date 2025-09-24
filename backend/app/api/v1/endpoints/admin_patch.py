from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import PlainTextResponse

from ....api.deps.admin_guard import ensure_admin_read_access
from ....core.database import get_session_factory
from ....services.admin.patch_generator import (
    PatchWindow,
    collect_community_decisions,
    build_patch,
    dump_yaml,
)


router = APIRouter(prefix="/admin/config", tags=["Admin-配置"])


@router.get("/patch", summary="导出社区决策 YAML Patch")
async def get_yaml_patch(
    request: Request,
    since: Optional[str] = Query(default=None, description="起始时间(ISO8601)；默认=24h内"),
) -> PlainTextResponse:
    ensure_admin_read_access(request)

    def parse_iso(ts: Optional[str]) -> Optional[datetime]:
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail="invalid since parameter") from exc

    end = datetime.now(timezone.utc)
    start = parse_iso(since) or (end - timedelta(hours=24))

    session_factory = get_session_factory()
    async with session_factory() as session:
        decisions = await collect_community_decisions(session, PatchWindow(start, end))
        patch = build_patch(decisions)
        text = dump_yaml(patch)
        return PlainTextResponse(text, media_type="text/yaml")
