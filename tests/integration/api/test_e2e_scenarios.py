"""
E2E scenario tests (safe subset)

Focus on endpoints that do not require external DB/queue by leveraging
SSE test endpoint and status fallback.
"""

import json
import uuid

import pytest

from .base import IntegrationTestBase


@pytest.mark.integration
class TestE2EScenarios(IntegrationTestBase):
    async def test_minimal_e2e_with_fallback(self, api_client, build_url):
        # 1) API info
        info = await api_client.get("/api")
        assert info.status_code == 200
        data = info.json()
        assert "api_version" in data

        # 2) SSE test stream
        task_id = str(uuid.uuid4())
        sse_url = self.url(build_url, f"/stream/{task_id}/test")
        saw_connected = False
        async with api_client.stream("GET", sse_url) as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    payload = json.loads(line[len("data: "):])
                    if payload.get("type") == "connected":
                        saw_connected = True
                    if payload.get("type") in ("completed", "error"):
                        break
        assert saw_connected

        # 3) Status with DB fallback
        status_url = self.url(build_url, f"/status/{task_id}")
        status_resp = await api_client.get(status_url)
        assert status_resp.status_code == 200
        status_json = status_resp.json()
        assert status_json["status"] == "success"
        assert status_json["data"]["task_id"] == task_id
        # Fallback mode is expected in environments without DB
        assert status_json["data"].get("_fallback_mode", True) is True


@pytest.mark.integration
@pytest.mark.skip(reason="Full E2E requires real DB, Redis and Celery queue")
class TestFullUserJourney(IntegrationTestBase):
    async def test_new_user_first_analysis(self, api_client, build_url):
        # Placeholder for full journey: register -> login -> analyze -> status -> report
        assert True

