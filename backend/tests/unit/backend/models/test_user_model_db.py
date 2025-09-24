from __future__ import annotations

import uuid
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.task import Task


def _bcrypt_dummy() -> str:
    # 符合 ^\$2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{53}$
    return "$2b$12$" + ("A" * 53)


def test_user_email_format_constraint(sync_db_session: "object") -> None:
    u = User(email="bad-email", password_hash=_bcrypt_dummy())
    sync_db_session.add(u)
    with pytest.raises(IntegrityError):
        sync_db_session.commit()
    sync_db_session.rollback()


def test_user_password_hash_format_constraint(sync_db_session: "object") -> None:
    u = User(email="ok@example.com", password_hash="not-bcrypt")
    sync_db_session.add(u)
    with pytest.raises(IntegrityError):
        sync_db_session.commit()
    sync_db_session.rollback()


def test_delete_user_cascades_tasks(sync_db_session: "object") -> None:
    # 创建用户
    u = User(email="cascade@example.com", password_hash=_bcrypt_dummy())
    sync_db_session.add(u)
    sync_db_session.flush()

    # 创建任务（FK ondelete=cascade）
    t = Task(user_id=u.id, product_description="demo task")
    sync_db_session.add(t)
    sync_db_session.commit()

    tid = t.id
    # 删除用户
    sync_db_session.delete(u)
    sync_db_session.commit()

    # 任务应被级联删除
    assert sync_db_session.get(Task, tid) is None

