"""
Analyze endpoint integration (safe subset)

Covers validation-only scenarios that do not require a real DB,
so they can run in any environment via ASGI in-process.
"""

from typing import Any, Callable, Sequence

import asyncio
import httpx
import pytest

from .base import IntegrationTestBase


@pytest.mark.integration
class TestAnalyzeValidation(IntegrationTestBase):
    async def test_create_analysis_task_invalid_length_422(
        self, api_client: httpx.AsyncClient, build_url: Callable[[str], str]
    ) -> None:
        url = self.url(build_url, "/analyze/")
        payload = {"product_description": "too short"}  # < 10 chars after strip
        resp = await api_client.post(url, json=payload)
        assert resp.status_code == 422

    async def test_create_analysis_task_blocked_pattern_400(
        self, api_client: httpx.AsyncClient, build_url: Callable[[str], str]
    ) -> None:
        url = self.url(build_url, "/analyze/")
        # Valid length but contains blocked SQL-injection pattern -> business validator -> 400
        text = "This description is long enough but contains DROP TABLE directive"
        payload = {"product_description": text}
        resp = await api_client.post(url, json=payload)
        # Endpoint uses ContentValidator (raises ValueError) -> HTTP 400
        assert resp.status_code == 400
        body = resp.json()
        assert "detail" in body


@pytest.mark.integration
class TestAnalyzeFlowSimulated(IntegrationTestBase):
    async def test_task_cancellation_endpoint(
        self, api_client: httpx.AsyncClient, build_url: Callable[[str], str]
    ) -> None:
        # cancel endpoint exists and returns success envelope
        task_id = "00000000-0000-0000-0000-000000000000"
        url = self.url(build_url, f"/analyze/{task_id}/cancel")
        resp = await api_client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "success"
        assert data.get("data", {}).get("action") == "cancel_requested"

    async def test_complete_analysis_workflow_with_fallback(
        self, api_client: httpx.AsyncClient, build_url: Callable[[str], str]
    ) -> None:
        # Simulate: stream test events -> poll status (fallback) -> expect success envelope
        import json as _json
        import uuid as _uuid

        task_id = str(_uuid.uuid4())

        # 1) stream a short test sequence (establish connection)
        stream_url = self.url(build_url, f"/stream/{task_id}/test")
        saw_connected = False
        async with api_client.stream("GET", stream_url) as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    payload = _json.loads(line[len("data: "):])
                    if payload.get("type") == "connected":
                        saw_connected = True
                        break
        assert saw_connected

        # 2) poll status (DB will fallback to mock)
        status_url = self.url(build_url, f"/status/{task_id}")
        status_resp = await api_client.get(status_url)
        assert status_resp.status_code == 200
        status_json = status_resp.json()
        assert status_json["status"] == "success"
        assert status_json["data"]["task_id"] == task_id
        assert status_json["data"].get("_fallback_mode", True) is True

    async def test_concurrent_analysis_tasks_simulated(
        self, api_client: httpx.AsyncClient, build_url: Callable[[str], str]
    ) -> None:
        # Open multiple test streams and verify status for each
        import uuid as _uuid

        ids = [str(_uuid.uuid4()) for _ in range(3)]
        stream_urls = [self.url(build_url, f"/stream/{tid}/test") for tid in ids]
        status_urls = [self.url(build_url, f"/status/{tid}") for tid in ids]

        async def start_stream(u: str) -> None:
            async with api_client.stream("GET", u) as resp:
                assert resp.status_code == 200
                # read one data line then exit
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        break

        await asyncio.gather(*[start_stream(u) for u in stream_urls])

        async def check_status(u: str) -> bool:
            response = await api_client.get(u)
            if response.status_code != 200:
                return False
            body: dict[str, Any] = response.json()
            return body.get("status") == "success"

        results = await asyncio.gather(*[check_status(u) for u in status_urls])
        assert all(results)


@pytest.mark.integration
@pytest.mark.skip(reason="Requires real DB and task queue to reach success path")
class TestAnalyzeHappyPath(IntegrationTestBase):
    async def test_create_analysis_task_success(
        self, api_client: httpx.AsyncClient, build_url: Callable[[str], str]
    ) -> None:
        url = self.url(build_url, "/analyze/")
        payload = {
            "product_description": (
                "We help SMBs monitor Reddit for authentic customer signals and pain points"
            )
        }
        resp = await api_client.post(url, json=payload)
        assert resp.status_code == 201
