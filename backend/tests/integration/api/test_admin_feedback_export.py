from __future__ import annotations

import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@pytest.mark.integration
def test_export_feedback_events_json_and_csv_from_file_fallback(
    monkeypatch: Any, tmp_path: Path, client: Any
) -> None:
    # 放行权限
    import app.middleware.jwt_middleware as jm
    import app.api.v1.endpoints.admin_feedback as fb_mod

    monkeypatch.setattr(jm, "has_permission_in_request", lambda *a, **k: True, raising=False)
    # 强制 DB/Redis 均失败，走 JSONL 回放文件
    monkeypatch.setattr(fb_mod, "get_session_factory", lambda: (_ for _ in ()).throw(RuntimeError("db off")))
    monkeypatch.setattr(fb_mod, "get_redis_client", lambda: (_ for _ in ()).throw(RuntimeError("redis off")))

    # 将 FALLBACK_FILE 指到临时路径
    fallback_file = tmp_path / "feedback_events.jsonl"
    monkeypatch.setattr(fb_mod, "FALLBACK_FILE", fallback_file, raising=False)

    now = datetime.now(timezone.utc)
    sample_rows = [
        {
            "event_id": "e1",
            "timestamp": _iso(now - timedelta(hours=1)),
            "request_id": "r1",
            "source": "frontend",
            "event_type": "analysis_rating",
            "task_id": "t1",
            "analysis_id": "a1",
            "user_id": "u1",
            "rating": "up",
            "reason": "good",
            "comment": "ok",
            "insight_id": None,
            "flag": None,
            "tags": ["tag1", "tag2"],
            "metric_name": None,
            "metric_value": None,
            "metric_unit": None,
            "context": {"k": "v"},
        },
        {
            "event_id": "e2",
            "timestamp": _iso(now - timedelta(minutes=10)),
            "request_id": "r2",
            "source": "frontend",
            "event_type": "insight_flag",
            "task_id": "t2",
            "analysis_id": "a2",
            "user_id": "u2",
            "rating": None,
            "reason": "bad",
            "comment": "hmm",
            "insight_id": "ins_2",
            "flag": "duplicate",
            "tags": [],
            "metric_name": None,
            "metric_value": None,
            "metric_unit": None,
            "context": {},
        },
    ]

    # 写入 JSONL
    with fallback_file.open("w", encoding="utf-8") as f:
        for row in sample_rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")

    # JSON 输出
    r_json = client.get("/api/v1/admin/feedback/export?format=json")
    assert r_json.status_code == 200
    body = r_json.json()
    assert body.get("count") == 2 and isinstance(body.get("items"), list)

    # CSV 输出
    r_csv = client.get("/api/v1/admin/feedback/export?format=csv")
    assert r_csv.status_code == 200
    assert r_csv.headers.get("content-type", "").startswith("text/csv")
    assert "attachment; filename=feedback_events_" in r_csv.headers.get("content-disposition", "")
    text = r_csv.text
    # 基本列头 + 两条记录
    assert "event_id,timestamp,request_id,source,event_type,task_id,analysis_id,user_id" in text
    assert text.count("\n") >= 3


@pytest.mark.integration
def test_export_feedback_events_range_filter(
    monkeypatch: Any, tmp_path: Path, client: Any
) -> None:
    import app.middleware.jwt_middleware as jm
    import app.api.v1.endpoints.admin_feedback as fb_mod

    monkeypatch.setattr(jm, "has_permission_in_request", lambda *a, **k: True, raising=False)
    monkeypatch.setattr(fb_mod, "get_session_factory", lambda: (_ for _ in ()).throw(RuntimeError("db off")))
    monkeypatch.setattr(fb_mod, "get_redis_client", lambda: (_ for _ in ()).throw(RuntimeError("redis off")))

    fallback_file = tmp_path / "feedback_events.jsonl"
    monkeypatch.setattr(fb_mod, "FALLBACK_FILE", fallback_file, raising=False)

    now = datetime.now(timezone.utc)
    rows = [
        {"event_id": "old", "timestamp": _iso(now - timedelta(days=2))},
        {"event_id": "in", "timestamp": _iso(now - timedelta(hours=3))},
        {"event_id": "new", "timestamp": _iso(now - timedelta(minutes=5))},
    ]
    with fallback_file.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r))
            f.write("\n")

    start = _iso(now - timedelta(hours=4))
    end = _iso(now - timedelta(hours=1))
    r = client.get(f"/api/v1/admin/feedback/export?format=json&start={start}&end={end}")
    assert r.status_code == 200
    body = r.json()
    ids = {item.get("event_id") for item in body.get("items", [])}
    assert ids == {"in"}

