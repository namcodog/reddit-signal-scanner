"""
SSE integration tests (in-process ASGI)

Covers the lightweight /api/v1/stream/{task_id}/test endpoint that
does not depend on external DB/Redis.
"""

import asyncio
import json
import uuid

import pytest

from .base import IntegrationTestBase


@pytest.mark.integration
class TestSSEIntegration(IntegrationTestBase):
    async def test_sse_connection_lifecycle(self, api_client, build_url):
        task_id = str(uuid.uuid4())
        url = self.url(build_url, f"/stream/{task_id}/test")

        received = []
        async with api_client.stream("GET", url) as resp:
            assert resp.status_code == 200
            # consume a few SSE lines
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    payload = json.loads(line[len("data: "):])
                    received.append(payload)
                    if payload.get("type") in ("completed", "error"):
                        break

        # basic shape assertions
        assert any(e.get("type") == "connected" for e in received)
        assert received[-1]["type"] in ("completed", "error")

    async def test_sse_event_sequence_has_progress(self, api_client, build_url):
        task_id = str(uuid.uuid4())
        url = self.url(build_url, f"/stream/{task_id}/test")

        saw_progress = False
        async with api_client.stream("GET", url) as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    payload = json.loads(line[len("data: "):])
                    if payload.get("type") == "progress":
                        saw_progress = True
                        break

        assert saw_progress

    async def test_sse_concurrent_clients(self, api_client, build_url):
        # Open 3 concurrent SSE test streams and ensure each sees at least one event
        task_id = str(uuid.uuid4())
        url = self.url(build_url, f"/stream/{task_id}/test")

        async def consume_one() -> int:
            count = 0
            async with api_client.stream("GET", url) as resp:
                assert resp.status_code == 200
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        count += 1
                        if count >= 2:
                            break
            return count

        results = await asyncio.gather(consume_one(), consume_one(), consume_one())
        assert all(c >= 2 for c in results)

    async def test_sse_error_recovery_on_invalid_id(self, api_client, build_url):
        # invalid task_id (too short) should return 400
        url = self.url(build_url, "/stream/x/test")
        resp = await api_client.get(url)
        assert resp.status_code == 400
