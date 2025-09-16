"""Common fixtures for integration API tests."""

from collections.abc import AsyncIterator
from typing import Any, Callable, cast

import httpx
import pytest
from fastapi import FastAPI
from starlette.types import ASGIApp

from backend.app.main import app as fastapi_app


@pytest.fixture(scope="session")
def app() -> FastAPI:
    return fastapi_app


@pytest.fixture(scope="session")
async def api_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=cast(Any, app))
    client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def build_url() -> Callable[[str], str]:
    return lambda path: path
