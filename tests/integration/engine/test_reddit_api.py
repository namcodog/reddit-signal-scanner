import pytest

from backend.app.services.reddit_client import create_reddit_client


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_reddit_client_uses_mock_and_basic_calls_work() -> None:
    client = await create_reddit_client()
    try:
        # Only call methods that the mock supports safely without strict data validation
        exists = await client.check_subreddit_exists("r/test")
        assert exists is True

        info = await client.get_community_info("r/test")
        assert info is not None
        assert "name" in info
        assert "subscribers" in info
    finally:
        await client.close()

