from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.services.task_status_service import TaskStatusService


def test_convert_row_to_task_info_includes_report_and_times() -> None:
    service = TaskStatusService(db=MagicMock())

    now = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    analysis_id = uuid.uuid4()
    row = {
        "status": "completed",
        "created_at": now,
        "updated_at": now,
        "started_at": now,
        "completed_at": now,
        "error_message": None,
        "analysis_id": analysis_id,
    }

    task_id = str(uuid.uuid4())
    task_info = service._convert_row_to_task_info(row, task_id)

    assert task_info is not None
    assert task_info.task_id == task_id
    assert task_info.status.value == "completed"
    assert task_info.progress == 100
    assert task_info.report_id == str(analysis_id)
    assert task_info.started_at is not None
    assert task_info.completed_at is not None
    assert task_info.estimated_completion == task_info.completed_at
