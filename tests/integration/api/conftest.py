import pytest
from typing import AsyncIterator, Callable
from httpx import ASGITransport, AsyncClient

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
async def api_client() -> AsyncIterator[AsyncClient]:
    # Use ASGITransport without lifespan to be compatible with current httpx version
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
