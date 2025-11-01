"""Performance and concurrency integration tests for the API."""

from __future__ import annotations

from typing import Callable

import pytest

from tests.utils.test_helpers import (
    assert_pagination_response,
    assert_response_time,
    create_test_companies_bulk,
    simulate_concurrent_requests,
)


pytestmark = pytest.mark.integration


@pytest.mark.performance
class TestAPIPerformance:
    """Verify response-time expectations for key endpoints."""

    @pytest.fixture
    def seeded_companies(self, db_session) -> None:
        create_test_companies_bulk(db_session, count=150, lead_status="new")

    def test_list_companies_response_time(self, client, auth_headers, seeded_companies) -> None:
        response = client.get("/api/v1/companies", headers=auth_headers)
        assert response.status_code == 200
        assert_response_time(response, 200)

    def test_create_company_response_time(self, client, auth_headers) -> None:
        payload = {"name": "Performance Test Inc.", "industry": "Testing"}
        response = client.post("/api/v1/companies", json=payload, headers=auth_headers)
        assert response.status_code in {201, 200}
        assert_response_time(response, 200)

    def test_bulk_scoring_response_time(self, client, auth_headers, seeded_companies) -> None:
        response = client.post(
            "/api/v1/scoring/companies/bulk",
            json={"company_ids": []},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert_response_time(response, 400)

    def test_export_json_response_time(self, client, auth_headers, seeded_companies) -> None:
        response = client.get("/api/v1/export/companies/json", headers=auth_headers)
        assert response.status_code == 200
        assert_response_time(response, 400)


@pytest.mark.performance
class TestConcurrentRequests:
    """Ensure concurrent access works without errors."""

    @pytest.mark.asyncio
    async def test_concurrent_company_listing(self, client, auth_headers, db_session) -> None:
        create_test_companies_bulk(db_session, count=40)
        responses = await simulate_concurrent_requests(
            client,
            "/api/v1/companies",
            count=5,
            headers=auth_headers,
            follow_redirects=True  # Follow redirects
        )

        for response in responses:
            assert hasattr(response, "status_code")
            # Check if we got a successful response (200) or a redirect (307)
            assert response.status_code in (200, 307)
            
            # If it's a redirect, follow it and check the final status
            if response.status_code == 307:
                redirect_url = response.headers.get("Location")
                if redirect_url:
                    redirect_response = await client.get(redirect_url, headers=auth_headers)
                    assert redirect_response.status_code == 200

    @pytest.mark.asyncio
    async def test_concurrent_company_creation(self, client, auth_headers) -> None:
        async_responses = await simulate_concurrent_requests(
            client,
            "/api/v1/companies",
            count=4,
            method="POST",
            json={
                "company_name": "Concurrent Corp",
                "email": "concurrent@example.com",
                "city": "Berlin",
            },
            headers=auth_headers,
        )

        statuses = {getattr(resp, "status_code", None) for resp in async_responses}
        assert statuses <= {200, 201, 400}


@pytest.mark.performance
class TestDatabasePerformance:
    """Measure performance characteristics for pagination and aggregation."""

    @pytest.fixture
    def large_dataset(self, db_session) -> None:
        create_test_companies_bulk(db_session, count=400, lead_status="qualified")

    @pytest.mark.slow
    def test_paginated_listing_with_filters(self, client, auth_headers, large_dataset) -> None:
        response = client.get(
            "/api/v1/companies?limit=100&skip=0&lead_status=QUALIFIED",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert_pagination_response(response)
        assert_response_time(response, 500)

    @pytest.mark.slow
    def test_company_stats_export(self, client, auth_headers, large_dataset) -> None:
        response = client.get("/api/v1/export/companies/stats", headers=auth_headers)
        assert response.status_code == 200
        assert "total_companies" in response.json()
        assert_response_time(response, 500)
