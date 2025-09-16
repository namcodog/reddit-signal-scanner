"""
Basic performance checks for API endpoints using in-process ASGI client.
These are lightweight and environment-agnostic.
"""

import asyncio
import time
from typing import Callable, List

import httpx
import pytest


@pytest.mark.integration
class TestPerformance:
    async def test_api_response_times(
        self, api_client: httpx.AsyncClient, build_url: Callable[[str], str]
    ) -> None:
        # measure /api and /health
        start = time.perf_counter()
        r1 = await api_client.get(build_url('/api'))
        t1 = time.perf_counter() - start
        assert r1.status_code == 200

        start = time.perf_counter()
        r2 = await api_client.get(build_url('/health'))
        t2 = time.perf_counter() - start
        assert r2.status_code == 200

        # thresholds generous for CI containers
        assert t1 < 2.0
        assert t2 < 2.0

    async def test_concurrent_requests_small(
        self, api_client: httpx.AsyncClient, build_url: Callable[[str], str]
    ) -> None:
        # 20 concurrent /api requests should succeed quickly
        async def one() -> httpx.Response:
            return await api_client.get(build_url('/api'))

        start = time.perf_counter()
        res = await asyncio.gather(*[one() for _ in range(20)])
        elapsed = time.perf_counter() - start

        assert all(r.status_code == 200 for r in res)
        # total elapsed should remain small in-process
        assert elapsed < 3.0
