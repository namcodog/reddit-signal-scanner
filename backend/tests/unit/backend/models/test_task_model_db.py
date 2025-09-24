from __future__ import annotations

from app.models.user import User
from app.models.task import Task


def _bcrypt_dummy() -> str:
    return "$2b$12$" + ("A" * 53)


def test_task_default_status_pending(sync_db_session: "object") -> None:
    u = User(email="task@example.com", password_hash=_bcrypt_dummy())
    sync_db_session.add(u)
    sync_db_session.flush()

    t = Task(user_id=u.id, product_description="p")
    sync_db_session.add(t)
    sync_db_session.commit()

    got = sync_db_session.get(Task, t.id)
    assert got is not None
    # server_default 应赋值为 'pending'
    assert str(getattr(got, "status", "")) == "pending"

