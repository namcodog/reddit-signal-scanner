"""User dashboard endpoints integration tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.dependencies import get_current_user
from app.models import Task, User
from app.models.task import TaskStatus
from app.models.user import MembershipLevel
from app.main import app
from backend.tests.conftest import DatabaseTestFactory


@pytest.mark.asyncio
async def test_user_dashboard_endpoints(client: TestClient, db_session: AsyncSession) -> None:
    """验证历史记录、使用统计和会员接口。"""

    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    user = User(
        **DatabaseTestFactory.minimal_valid_user(
            id=user_id,
            tenant_id=tenant_id,
            membership_level=MembershipLevel.PRO,
        )
    )
    db_session.add(user)
    await db_session.flush()

    tasks = [
        Task(
            **DatabaseTestFactory.minimal_valid_task(
                user_id=user_id,
                status=TaskStatus.PENDING,
                created_at=now - timedelta(minutes=5),
                updated_at=now - timedelta(minutes=4),
            )
        ),
        Task(
            **DatabaseTestFactory.minimal_valid_task(
                user_id=user_id,
                status=TaskStatus.PROCESSING,
                created_at=now - timedelta(minutes=3),
                updated_at=now - timedelta(minutes=2),
            )
        ),
        Task(
            **DatabaseTestFactory.minimal_valid_task(
                user_id=user_id,
                status=TaskStatus.COMPLETED,
                created_at=now - timedelta(minutes=10),
                updated_at=now - timedelta(minutes=9),
                completed_at=now - timedelta(minutes=9),
            )
        ),
        Task(
            **DatabaseTestFactory.minimal_valid_task(
                user_id=user_id,
                status=TaskStatus.FAILED,
                created_at=now - timedelta(minutes=20),
                updated_at=now - timedelta(minutes=19),
                error_message="网络错误",
            )
        ),
        Task(
            **DatabaseTestFactory.minimal_valid_task(
                user_id=user_id,
                status=TaskStatus.COMPLETED,
                created_at=(now - timedelta(days=40)),
                updated_at=(now - timedelta(days=39)),
                completed_at=(now - timedelta(days=39)),
            )
        ),
    ]

    db_session.add_all(tasks)
    await db_session.commit()

    current_user = CurrentUser(
        user_id=str(user_id),
        tenant_id=str(tenant_id),
        email=user.email,  # type: ignore[arg-type]
        permissions=[],
        auth_time=now,
    )

    app.dependency_overrides[get_current_user] = lambda: current_user

    try:
        history_response = client.get(
            "/api/v1/users/me/history",
            params={"limit": 3},
        )
        assert history_response.status_code == 200
        history_data = history_response.json()
        assert isinstance(history_data, list)
        assert len(history_data) == 3
        assert history_data[0]["status"] in {"pending", "processing"}

        usage_response = client.get("/api/v1/users/me/usage")
        assert usage_response.status_code == 200
        usage_data = usage_response.json()
        assert usage_data["total_tasks"] == 5
        assert usage_data["completed_tasks"] == 2
        assert usage_data["failed_tasks"] == 1
        assert usage_data["active_tasks"] == 1
        assert usage_data["pending_tasks"] == 1
        assert usage_data["current_month_total"] == 4
        assert usage_data["current_month_quota"] == 100
        assert usage_data["remaining_quota"] == 96

        membership_response = client.get("/api/v1/users/me/membership")
        assert membership_response.status_code == 200
        membership_data = membership_response.json()
        assert membership_data["level"] == "pro"
        assert membership_data["quota"] == 100
        assert membership_data["used_this_month"] == 4
        assert "enterprise" in membership_data["upgrade_options"]

        upgrade_response = client.post(
            "/api/v1/users/me/membership",
            json={"target_level": "enterprise"},
        )
        assert upgrade_response.status_code == 200
        upgraded = upgrade_response.json()
        assert upgraded["level"] == "enterprise"
        assert upgraded["quota"] is None

        # 再次获取使用统计，额度应显示为不限
        usage_after_upgrade = client.get("/api/v1/users/me/usage")
        assert usage_after_upgrade.status_code == 200
        usage_after_data = usage_after_upgrade.json()
        assert usage_after_data["current_month_quota"] is None
        assert usage_after_data["remaining_quota"] is None

    finally:
        app.dependency_overrides.pop(get_current_user, None)
