from __future__ import annotations

from sqlalchemy import text, create_engine
from app.core.config import get_settings


def test_task_status_enum_exists() -> None:
    # 使用同步连接检查枚举类型存在与成员
    sync_url = get_settings().database_url_sync
    engine = create_engine(sync_url, future=True)
    try:
        with engine.connect() as conn:
            res = conn.execute(text("SELECT unnest(enum_range(NULL::task_status))::text")).fetchall()
            values = [r[0] for r in res]
            assert set(["pending", "processing", "completed", "failed"]).issubset(set(values))
    finally:
        engine.dispose()
