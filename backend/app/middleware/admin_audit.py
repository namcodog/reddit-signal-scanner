from __future__ import annotations

import json
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..schemas.admin.audit import AuditRecord


AUDIT_FILE = Path("backend/data/admin_audit.jsonl")


class AdminAuditMiddleware(BaseHTTPMiddleware):
    """记录 /api/v1/admin/* 请求的审计日志（JSONL）。

    字段：timestamp/trace_id/user_id/path/method/action/status_code
    输出：backend/data/admin_audit.jsonl
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        is_admin_scope = request.url.path.startswith("/api/v1/admin/")
        response: Response
        response = await call_next(request)

        if is_admin_scope:
            try:
                record = AuditRecord(
                    timestamp=_utc_iso(),
                    trace_id=getattr(request.state, "request_id", None),
                    user_id=str(getattr(request.state, "user_id", "")) or None,
                    path=request.url.path,
                    method=request.method,
                    action=_infer_action(request.url.path),
                    status_code=int(getattr(response, "status_code", 0)),
                )
                _append_audit(record)
            except Exception:
                # 审计记录不影响主流程
                pass

        return response


def _utc_iso() -> str:
    import datetime as _dt

    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _infer_action(path: str) -> str:
    # 粗粒度映射，满足审计检索
    if "/admin/decisions/community" in path:
        return "community_decision"
    if "/admin/config/patch" in path:
        return "export_patch"
    if "/admin/feedback/analysis" in path:
        return "analysis_feedback"
    if "/admin/feedback/summary" in path:
        return "feedback_summary"
    if "/admin/analysis/" in path:
        return "analysis_query"
    if "/admin/communities/summary" in path:
        return "communities_query"
    return "admin_operation"


def _append_audit(record: AuditRecord) -> None:
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record.model_dump(), ensure_ascii=False))
        f.write("\n")
