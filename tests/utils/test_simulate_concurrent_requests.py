import pytest

from tests.utils.test_helpers import simulate_concurrent_requests


@pytest.mark.asyncio
async def test_simulate_concurrent_requests_returns_httpx_responses(async_client):
    responses = await simulate_concurrent_requests(async_client, "/health", 2)

    assert len(responses) == 2
    assert all(getattr(response, "status_code", None) is not None for response in responses)
    assert all(getattr(response, "is_success", False) for response in responses)
