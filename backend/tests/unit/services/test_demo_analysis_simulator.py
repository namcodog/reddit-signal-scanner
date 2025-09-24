"""
DemoAnalysisSimulator 单元测试

验证：
- 状态推进（pending -> running -> completed）
- 进度合理（最小5%，完成100%）
- 完成态提供 report_id
- get_report 仅在完成态返回数据
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.schemas.task import TaskStatus
from app.services.demo_analysis_simulator import demo_analysis_simulator


def test_demo_simulator_status_progression() -> None:
    sim = demo_analysis_simulator()

    # 保证启用
    assert sim.enabled is True

    task_id = str(uuid.uuid4())
    sim.register_task(task_id, "测试任务描述")

    # 刚注册：应为 PENDING，进度至少5%
    info = sim.enrich_task_info(task_id, None)
    assert info is not None
    assert info.status == TaskStatus.PENDING
    assert 5 <= info.progress < 100
    assert info.report_id is None

    # 人为推进3秒：应为 RUNNING
    now = datetime.now(timezone.utc)
    sim._tasks[task_id].created_at = now - timedelta(seconds=3)
    running_info = sim.enrich_task_info(task_id, None)
    assert running_info is not None
    assert running_info.status == TaskStatus.RUNNING
    assert 5 <= running_info.progress < 100
    assert running_info.report_id is None

    # 推进到完成：应为 COMPLETED，progress=100 且有 report_id
    sim._tasks[task_id].created_at = now - timedelta(seconds=12)
    completed_info = sim.enrich_task_info(task_id, None)
    assert completed_info is not None
    assert completed_info.status == TaskStatus.COMPLETED
    assert completed_info.progress == 100
    assert completed_info.report_id is not None

    # get_report 仅在完成态可用
    report = sim.get_report(task_id)
    assert report is not None
    assert report.task_id == task_id

