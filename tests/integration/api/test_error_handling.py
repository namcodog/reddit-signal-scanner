"""
Error handling middleware integration tests (dev mode)

Verifies /dev/test-error is caught and returns unified error payload.
"""

from typing import Callable

import httpx
import pytest


@pytest.mark.integration
async def test_dev_test_error_returns_unified_payload(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.get("/dev/test-error")
    assert resp.status_code == 500
    data = resp.json()
    assert data.get("status") == "error"
    assert data.get("error_type") == "internal_error"
    assert "message" in data
    assert "timestamp" in data
    assert "request_id" in data


@pytest.mark.integration
async def test_status_fallback_returns_guidance(
    api_client: httpx.AsyncClient, build_url: Callable[[str], str]
) -> None:
    # Status endpoint should fallback and include polling guidance key
    task_id = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    url = build_url(f"/status/{task_id}")
    r = await api_client.get(url)
    assert r.status_code == 200
    j = r.json()
    assert j.get("status") == "success"
    guidance = j["data"].get("_polling_guidance")
    assert guidance is not None


@pytest.mark.integration
async def test_stream_invalid_id_returns_400(
    api_client: httpx.AsyncClient, build_url: Callable[[str], str]
) -> None:
    r = await api_client.get(build_url("/stream/x/test"))
    assert r.status_code == 400
