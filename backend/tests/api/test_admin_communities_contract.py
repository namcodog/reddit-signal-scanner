from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest
from starlette.requests import Request

from app.models.community_cache import CommunityCache
from app.api.v1.endpoints.admin_communities import get_communities_summary


@pytest.mark.asyncio
async def test_admin_communities_summary_contract(sync_db_session: "object") -> None:
    # 准备一条社区记录
    now = datetime.now(timezone.utc)
    row = CommunityCache(
        community_name="r/test_contract",
        last_crawled_at=now - timedelta(hours=10),
        ttl_seconds=3600,
        posts_cached=10,
        quality_score=Decimal("0.70"),
        hit_count=5,
        crawl_priority=50,
    )
    sync_db_session.add(row)
    sync_db_session.commit()

    # 构造带有 admin 权限的 Request
    scope = {"type": "http", "method": "GET", "path": "/api/v1/admin/communities/summary", "headers": []}
    request = Request(scope)
    request.state.permissions = ["admin"]
    request.state.request_id = "trace-test"

    resp = await get_communities_summary(request, q="r/test", status=None, sort="cscore_desc", offset=0, limit=10)

    # 断言包装结构
    assert getattr(resp, "code", None) == 0
    assert hasattr(resp, "data")
    assert hasattr(resp.data, "items")
    assert hasattr(resp.data, "total")
    assert isinstance(resp.data.items, list)
    assert resp.data.total >= 1
    # 至少包含我们插入的社区
    names = [it.community for it in resp.data.items]
    assert "r/test_contract" in names
