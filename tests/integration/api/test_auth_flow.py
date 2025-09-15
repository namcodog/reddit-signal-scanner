"""
Auth flow integration tests (placeholders)

These require a real database and configured auth services to pass.
We provide structure and skip by default, ready to enable later.
"""

import pytest

from .base import IntegrationTestBase


@pytest.mark.integration
@pytest.mark.skip(reason="Requires real DB and email/password users")
class TestAuthFlow(IntegrationTestBase):
    async def test_user_registration_login_flow(self, api_client, build_url):
        # register
        register_url = self.url(build_url, "/auth/register")
        payload = {
            "email": "john.doe@example.com",
            "password": "MySecurePassword123!",
            "confirm_password": "MySecurePassword123!",
        }
        reg = await api_client.post(register_url, json=payload)
        assert reg.status_code == 201

        # login
        login_url = self.url(build_url, "/auth/login")
        login = await api_client.post(
            login_url, json={"email": payload["email"], "password": payload["password"]}
        )
        assert login.status_code == 200
        tokens = login.json()
        assert "access_token" in tokens

    async def test_jwt_token_refresh(self, api_client, build_url):
        refresh_url = self.url(build_url, "/auth/refresh")
        # Requires a valid refresh token in Authorization header
        pytest.skip("Not enabled without token bootstrap")

    async def test_multi_tenant_isolation(self, api_client, build_url):
        pytest.skip("Will be enabled once multi-tenant data is seeded")

