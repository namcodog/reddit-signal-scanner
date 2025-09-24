from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from app.core.task_status import UnifiedTaskStatus
from app.schemas.task_status import TaskStatusSnapshot
from app.services.task_tracker import TaskTrackerV2


def test_build_event_payload_has_standard_fields() -> None:
    tracker = TaskTrackerV2(redis_client=MagicMock(), db_session=MagicMock())
    now = datetime.now(timezone.utc)
    snapshot = TaskStatusSnapshot(
        task_id=uuid4(),
        user_id=uuid4(),
        status=UnifiedTaskStatus.COMPLETED,
        progress=100,
        created_at=now - timedelta(minutes=2),
        updated_at=now,
        started_at=now - timedelta(minutes=1),
        completed_at=now,
        retry_count=0,
        report_id="analysis-123",
    )

    payload = tracker._build_event_payload(
        UnifiedTaskStatus.COMPLETED,
        snapshot,
        additional_data=None,
    )

    assert payload["task_id"] == str(snapshot.task_id)
    assert payload["status"] == "completed"
    assert payload["report_id"] == "analysis-123"
    assert payload["completed_at"] == payload["estimated_completion"]
    assert payload["created_at"] is not None
    assert payload["updated_at"] is not None
