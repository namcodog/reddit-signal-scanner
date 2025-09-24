from __future__ import annotations

import pytest
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.task import Task
from app.models.analysis import Analysis


def _bcrypt_dummy() -> str:
    return "$2b$12$" + ("A" * 53)


def test_analysis_json_schema_constraints(sync_db_session: "object") -> None:
    # 创建用户与任务
    u = User(email="a@b.com", password_hash=_bcrypt_dummy())
    sync_db_session.add(u)
    sync_db_session.flush()
    t = Task(user_id=u.id, product_description="demo")
    sync_db_session.add(t)
    sync_db_session.commit()

    # 无效 insights（缺少必需键）应违反约束
    bad = Analysis(
        task_id=t.id,
        insights={"foo": []},
        sources={"communities": [], "posts_analyzed": 1, "cache_hit_rate": 0.9},
        confidence_score=Decimal("0.8"),
        analysis_version=1,
    )
    sync_db_session.add(bad)
    with pytest.raises(IntegrityError):
        sync_db_session.commit()
    sync_db_session.rollback()

    # 有效结构应成功
    good = Analysis(
        task_id=t.id,
        insights={
            "pain_points": [
                {"description": "x", "frequency": 1, "sentiment_score": 0.5}
            ],
            "competitors": [],
            "opportunities": [],
        },
        sources={
            "communities": ["r/test"],
            "posts_analyzed": 10,
            "cache_hit_rate": 0.8,
        },
        confidence_score=Decimal("0.7"),
        analysis_version=1,
    )
    sync_db_session.add(good)
    sync_db_session.commit()

    got = sync_db_session.query(Analysis).filter(Analysis.task_id == t.id).one()
    assert got.confidence_percentage == float(good.confidence_score) * 100

