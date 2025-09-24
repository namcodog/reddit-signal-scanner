from __future__ import annotations

def test_feedback_events_rating_like(client: "object") -> None:
    payload = {
        "source": "user",
        "event_type": "analysis_rating",
        "task_id": "tsk_test",
        "rating": "like",
    }
    resp = client.post("/api/v1/feedback/events", json=payload)
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data.get("status") in ("success", "error")
    # 返回体包含 data.event_id，便于追踪
    assert "data" in data and "event_id" in data["data"]
