"""Integration Tests für Health API Endpoints."""

import pytest

from app.api import health as health_module

pytestmark = pytest.mark.integration


class TestHealthEndpoints:
    """Test Suite für Health Endpoints"""

    def test_health_check(self, client):
        """Test: Basic health check endpoint"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "environment" in data

    def test_detailed_health_check(self, client):
        """Test: Detailed health check with all dependencies"""
        response = client.get("/health/detailed")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert "checks" in data

        checks = data["checks"]
        assert "api" in checks
        assert "database" in checks
        assert "redis" in checks
        assert "ollama" in checks

        # API should always be healthy
        assert checks["api"] == "healthy"

    def test_readiness_check(self, client):
        """Test: Kubernetes readiness probe"""
        response = client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] in ["ready", "not_ready"]

        if data["status"] == "not_ready":
            assert "reason" in data

    def test_liveness_check(self, client):
        """Test: Kubernetes liveness probe"""
        response = client.get("/health/live")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "alive"
        assert "timestamp" in data

    def test_health_endpoints_response_time(self, client):
        """Test: Health endpoints respond quickly"""
        import time

        start = time.time()
        response = client.get("/health")
        duration = time.time() - start

        assert response.status_code == 200
        # Health check should respond quickly (allow generous margin for CI environments)
        assert duration < 0.5

    def test_health_check_headers(self, client):
        """Test: Health check returns correct headers"""
        response = client.get("/health")

        assert response.status_code == 200
        assert "content-type" in response.headers
        assert "application/json" in response.headers["content-type"]

    def test_detailed_health_check_db_failure(self, client, monkeypatch):
        """Test: Detailed health check handles DB failure."""

        async def failing_db_check():
            return False

        monkeypatch.setattr(health_module, "check_db_connection", failing_db_check)

        response = client.get("/health/detailed")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["checks"]["database"] == "unhealthy"

    def test_detailed_health_check_db_exception(self, client, monkeypatch):
        """Test: Detailed health check handles DB exception."""

        async def exploding_db_check():
            raise RuntimeError("db boom")

        monkeypatch.setattr(health_module, "check_db_connection", exploding_db_check)

        response = client.get("/health/detailed")

        assert response.status_code == 200
        data = response.json()
        assert "unhealthy" in data["checks"]["database"]
        assert "db boom" in data["checks"]["database"]

    def test_detailed_health_check_redis_exception(self, client, monkeypatch):
        """Test: Detailed health check handles Redis exception."""

        class FailingRateLimiter:
            async def connect(self):
                raise ConnectionError("redis down")

            async def close(self):
                pass

        monkeypatch.setattr("app.utils.rate_limiter.rate_limiter", FailingRateLimiter())

        response = client.get("/health/detailed")

        assert response.status_code == 200
        data = response.json()
        redis_status = data["checks"]["redis"]
        assert "unhealthy" in redis_status
        assert "redis down" in redis_status

    def test_detailed_health_check_ollama_exception(self, client, monkeypatch):
        """Test: Detailed health check handles Ollama exception."""
        import httpx

        class FailingClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def get(self, url):
                raise httpx.ConnectError("ollama unreachable")

        monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=5: FailingClient())

        response = client.get("/health/detailed")

        assert response.status_code == 200
        data = response.json()
        assert "unhealthy" in data["checks"]["ollama"]

    def test_detailed_health_check_ollama_success(self, client, monkeypatch):
        """Test: Detailed health check marks Ollama healthy on 200 response."""
        import httpx

        async def healthy_db_check():
            return True

        class DummyRateLimiter:
            async def connect(self):
                return None

            async def close(self):
                return None

        class HealthyClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def get(self, url):
                class Response:
                    status_code = 200

                return Response()

        monkeypatch.setattr(health_module, "check_db_connection", healthy_db_check)
        monkeypatch.setattr("app.utils.rate_limiter.rate_limiter", DummyRateLimiter())
        monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=5: HealthyClient())

        response = client.get("/health/detailed")

        assert response.status_code == 200
        data = response.json()
        assert data["checks"]["ollama"] == "healthy"

    def test_readiness_check_not_ready(self, client, monkeypatch):
        """Test: Readiness check returns not_ready when DB is down."""

        async def failing_db_check():
            return False

        monkeypatch.setattr(health_module, "check_db_connection", failing_db_check)

        response = client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "not_ready"
        assert "reason" in data
        assert "database" in data["reason"].lower()
