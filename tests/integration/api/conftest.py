import pytest
from typing import Any, AsyncIterator, Callable, cast

import httpx

from backend.app.main import app
from backend.app.core.config import get_settings


@pytest.fixture(scope="session")
def api_prefix() -> str:
    settings = get_settings()
    return settings.api_prefix


@pytest.fixture(scope="session")
def build_url(api_prefix: str) -> Callable[[str], str]:
    def _join(path: str) -> str:
        if path.startswith("/api/"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return f"{api_prefix}{path}"

    return _join


@pytest.fixture
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=cast(Any, app))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
