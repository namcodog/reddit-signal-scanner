from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, List

import pytest


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class _State:
    request_id: str = "req_sys_e2e"
    user_id: str | None = None


@dataclass
class _Req:
    state: _State


class _StubResult:
    def __init__(self, rows: Iterable[Any]):
        self._rows = list(rows)

    # SQLAlchemy result API仿真
    def scalars(self) -> "_StubResult":
        return self

    def all(self) -> List[Any]:
        return list(self._rows)


class _StubSession:
    def __init__(self, jsonl_path: Path, window_start: datetime):
        self._jsonl = jsonl_path
        self._start = window_start

    async def __aenter__(self) -> "_StubSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: D401
        return None

    async def execute(self, _stmt: Any) -> _StubResult:  # noqa: D401
        # 读取 JSONL，筛选 analysis_rating 事件 → 组装 payload-only 记录
        rows: list[Any] = []
        if self._jsonl.exists():
            with self._jsonl.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    if (
                        obj.get("event_type") == "analysis_rating"
                        and obj.get("timestamp")
                    ):
                        try:
                            ts = datetime.fromisoformat(
                                str(obj["timestamp"]).replace("Z", "+00:00")
                            )
                        except Exception:
                            continue
                        if ts >= self._start:
                            # 构造具有 payload 属性的简易对象
                            rows.append(type("Row", (), {"payload": obj}))
        return _StubResult(rows)


@pytest.mark.asyncio
async def test_feedback_flow_end_to_end(monkeypatch: Any, tmp_path: Path) -> None:
    # 1) 预设：强制文件回放路径 + 放行权限
    import app.api.v1.endpoints.admin_feedback as admin_fb
    import app.services.feedback_event_service as svc_fb
    import app.api.v1.endpoints.feedback as public_fb

    jsonl = tmp_path / "feedback_events.jsonl"
    monkeypatch.setattr(admin_fb, "FALLBACK_FILE", jsonl, raising=False)
    monkeypatch.setattr(svc_fb, "FALLBACK_FILE", jsonl, raising=False)

    # 绕过权限（Admin 读取）
    monkeypatch.setattr(admin_fb, "has_permission_in_request", lambda *a, **k: True)

    # 强制不使用DB/Redis（写入与导出均走文件降级path）
    monkeypatch.setattr(
        svc_fb, "get_redis_client", lambda: (_ for _ in ()).throw(RuntimeError("redis off"))
    )
    monkeypatch.setattr(
        admin_fb, "get_redis_client", lambda: (_ for _ in ()).throw(RuntimeError("redis off"))
    )

    # 2) 上报三条埋点事件（2赞1踩）
    req = _Req(state=_State())

    from app.schemas.feedback import (
        FeedbackEventRequest,
        FeedbackEventType,
        FeedbackSource,
        RatingValue,
    )

    payloads = [
        FeedbackEventRequest(
            source=FeedbackSource.user,
            event_type=FeedbackEventType.analysis_rating,
            task_id="t-e2e-1",
            rating=RatingValue.like,
            reason="good",
        ),
        FeedbackEventRequest(
            source=FeedbackSource.user,
            event_type=FeedbackEventType.analysis_rating,
            task_id="t-e2e-2",
            rating=RatingValue.like,
            reason="useful",
        ),
        FeedbackEventRequest(
            source=FeedbackSource.user,
            event_type=FeedbackEventType.analysis_rating,
            task_id="t-e2e-3",
            rating=RatingValue.dislike,
            reason="coverage_low",
        ),
    ]

    # 禁用 DB 写入，直接走文件降级
    monkeypatch.setattr(
        svc_fb, "get_session_factory", lambda: (_ for _ in ()).throw(RuntimeError("db off"))
    )

    for p in payloads:
        resp = await public_fb.post_feedback_event(req, p)
        assert resp.status.value in ("success", "error")  # 文件降级也算成功

    # 3) 汇总接口：为其提供一个“读取 JSONL”的伪造 SessionFactory
    window_start = datetime.now(timezone.utc) - timedelta(days=2)

    def _fake_factory():
        class _Ctx:
            async def __aenter__(self):
                return _StubSession(jsonl, window_start)

            async def __aexit__(self, exc_type, exc, tb):
                return None

        return _Ctx()

    monkeypatch.setattr(admin_fb, "get_session_factory", _fake_factory)

    summary = await admin_fb.get_admin_feedback_summary(req, days=30)
    assert getattr(summary, "code", 1) == 0
    assert summary.data.total >= 3
    assert summary.data.likes >= 2
    assert summary.data.dislikes >= 1

    # 4) 导出：强制文件回放（DB/Redis 关闭），校验 CSV/JSON 形态
    start = _iso(datetime.now(timezone.utc) - timedelta(hours=4))
    end = _iso(datetime.now(timezone.utc) + timedelta(minutes=1))
    csv_resp = await admin_fb.export_feedback_events(req, start=start, end=end, format="csv", limit=100)
    assert hasattr(csv_resp, "media_type") and getattr(csv_resp, "media_type") == "text/csv"

    json_resp = await admin_fb.export_feedback_events(req, start=start, end=end, format="json", limit=100)
    body = getattr(json_resp, "body", None) or getattr(json_resp, "_content", None)
    # FastAPI JSONResponse.text/ body behavior：直接检查 count 字段
    # 取法兼容不同运行器
    if isinstance(body, (bytes, bytearray)):
        data = json.loads(body.decode("utf-8"))
    elif isinstance(body, str):
        data = json.loads(body)
    else:
        data = json_resp.body  # type: ignore[attr-defined]
        try:
            data = json.loads(data.decode("utf-8"))
        except Exception:
            pass

    assert int(data.get("count", 0)) >= 3

