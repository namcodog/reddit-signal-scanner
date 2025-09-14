"""
Integration API fixtures

- In-process ASGI client for FastAPI app
- Helper to build API paths with configured prefix
"""

import asyncio
from typing import AsyncIterator, Callable

import pytest
from httpx import ASGITransport, AsyncClient

# Import FastAPI app and settings
from backend.app.main import app
from backend.app.core.config import get_settings


@pytest.fixture(scope="session")
def api_prefix() -> str:
    settings = get_settings()
    return settings.api_prefix


@pytest.fixture(scope="session")
def build_url(api_prefix: str) -> Callable[[str], str]:
    """Helper to join API prefix with a relative path.

    Accepts absolute paths as pass-through.
    """

    def _join(path: str) -> str:
        if path.startswith("/api/"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return f"{api_prefix}{path}"

    return _join


@pytest.fixture
async def api_client() -> AsyncIterator[AsyncClient]:
    """ASGI in-process HTTP client with lifespan enabled.

    Does not require running uvicorn or external network.
    """
    transport = ASGITransport(app=app, lifespan="on")
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

