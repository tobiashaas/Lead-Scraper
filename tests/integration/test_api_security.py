"""Security-focused integration tests for API endpoints."""

from __future__ import annotations

import jwt
import pytest

from tests.utils.test_helpers import (
    generate_path_traversal_payloads,
    generate_sql_injection_payloads,
    generate_xss_payloads,
)


pytestmark = pytest.mark.integration


@pytest.mark.security
class TestAuthenticationSecurity:
    """Authentication hardening scenarios and abuse cases."""

    @pytest.mark.parametrize("payload", generate_sql_injection_payloads())
    def test_login_sql_injection_attempt(self, client, payload: str) -> None:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": payload, "password": payload},
        )
        assert response.status_code in {401, 403}

    @pytest.mark.parametrize("payload", generate_xss_payloads())
    def test_register_xss_payload_rejected(self, client, payload: str) -> None:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": f"user_{hash(payload) & 0xffff}",
                "email": f"{hash(payload)}@example.com",
                "password": "SecurePass123!",
                "full_name": payload,
            },
        )
        assert response.status_code in {201, 400}
        if response.status_code == 201:
            assert payload not in response.text

    def test_bruteforce_lockout(self, client, auth_user) -> None:
        for _ in range(6):
            response = client.post(
                "/api/v1/auth/login",
                json={"username": auth_user.username, "password": "wrong"},
            )
            assert response.status_code == 401

        locked_resp = client.post(
            "/api/v1/auth/login",
            json={"username": auth_user.username, "password": "testpass123"},
        )
        assert locked_resp.status_code in {401, 403}

    def test_jwt_tampering_detected(self, client, auth_headers) -> None:
        access_token = auth_headers["Authorization"].split()[1]
        segments = access_token.split(".")
        assert len(segments) == 3
        tampered_payload_b64 = segments[1][::-1]
        tampered_token = f"{segments[0]}.{tampered_payload_b64}.{segments[2]}"
        protected_resp = client.get(
            "/api/v1/companies",
            headers={"Authorization": f"Bearer {tampered_token}"},
        )
        assert protected_resp.status_code in {401, 403}

    def test_refresh_token_signature_validation(self, client, auth_user) -> None:
        bogus_token = jwt.encode({"sub": auth_user.username, "type": "refresh"}, "wrong", algorithm="HS256")
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": bogus_token},
        )
        # 422 is valid for malformed token, 401/403 for invalid signature
        assert response.status_code in {401, 403, 422}

    def test_expired_access_token_denied(self, client, expired_token) -> None:
        response = client.get("/api/v1/companies", headers=expired_token)
        assert response.status_code in {401, 403}


@pytest.mark.security
class TestInputValidationSecurity:
    """Payload validation and injection prevention tests."""

    @pytest.mark.parametrize("payload", generate_sql_injection_payloads())
    def test_companies_search_sql_injection(self, client, auth_headers, payload: str) -> None:
        response = client.get(
            f"/api/v1/companies?search={payload}",
            headers=auth_headers,
        )
        assert response.status_code in {200, 400, 422}

    @pytest.mark.parametrize("payload", generate_xss_payloads())
    def test_company_create_xss(self, client, auth_headers, payload: str) -> None:
        response = client.post(
            "/api/v1/companies",
            headers=auth_headers,
            json={
                "company_name": payload,
                "email": f"{hash(payload)}@example.com",
                "city": "Berlin",
            },
        )
        assert response.status_code in {201, 400, 422}

    @pytest.mark.parametrize("payload", generate_path_traversal_payloads())
    def test_export_path_traversal(self, client, auth_headers, payload: str) -> None:
        response = client.get(
            f"/api/v1/export/companies/csv?lead_status={payload}",
            headers=auth_headers,
        )
        assert response.status_code in {200, 400, 422}

    def test_scraping_params_command_injection_like(self, client, auth_headers) -> None:
        response = client.post(
            "/api/v1/scraping/jobs",
            headers=auth_headers,
            json={
                "source_name": "11880",
                "city": "Berlin; rm -rf /",
                "max_pages": 1,
            },
        )
        assert response.status_code in {201, 400, 422, 404}


@pytest.mark.security
class TestAuthorizationSecurity:
    """Ensure users cannot cross boundaries or escalate privileges."""

    def test_user_cannot_access_another_users_webhook(self, client, auth_headers, second_auth_user) -> None:
        create_resp = client.post(
            "/api/v1/webhooks/",
            json={"url": "https://forbidden.test", "events": ["job.completed"]},
            headers=auth_headers,
        )
        assert create_resp.status_code == 200
        webhook_id = create_resp.json()["id"]

        second_token_resp = client.post(
            "/api/v1/auth/login",
            json={"username": second_auth_user.username, "password": "testpass123"},
        )
        second_access = second_token_resp.json()["access_token"]

        forbidden_resp = client.get(
            f"/api/v1/webhooks/{webhook_id}",
            headers={"Authorization": f"Bearer {second_access}"},
        )
        assert forbidden_resp.status_code == 403

    def test_non_admin_cannot_list_users(self, client, auth_headers) -> None:
        response = client.get("/api/v1/auth/users", headers=auth_headers)
        assert response.status_code in {403, 401}


@pytest.mark.security
class TestRateLimitingSecurity:
    """Validate rate limiting behaviour using the injected rate-limited client."""

    def test_rate_limiting_login_endpoint(self, rate_limited_client) -> None:
        last_response = None
        for _ in range(7):
            last_response = rate_limited_client.post(
                "/api/v1/auth/login",
                json={"username": "throttle", "password": "wrong"},
            )
        assert last_response is not None
        assert last_response.status_code == 429

    def test_rate_limiting_protected_endpoint(self, rate_limited_client, auth_headers) -> None:
        # Warm up to ensure authentication succeeds before hitting the limit
        for _ in range(rate_limited_client.threshold):
            resp = rate_limited_client.get("/api/v1/companies", headers=auth_headers)
            assert resp.status_code in {200, 401, 403}

        limited_resp = rate_limited_client.get("/api/v1/companies", headers=auth_headers)
        assert limited_resp.status_code == 429
