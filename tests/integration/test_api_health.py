"""
Integration Tests für Health API Endpoints
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthEndpoints:
    """Test Suite für Health Endpoints"""

    def test_health_check(self):
        """Test: Basic health check endpoint"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "environment" in data

    def test_detailed_health_check(self):
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

    def test_readiness_check(self):
        """Test: Kubernetes readiness probe"""
        response = client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] in ["ready", "not_ready"]

        if data["status"] == "not_ready":
            assert "reason" in data

    def test_liveness_check(self):
        """Test: Kubernetes liveness probe"""
        response = client.get("/health/live")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "alive"
        assert "timestamp" in data

    def test_health_endpoints_response_time(self):
        """Test: Health endpoints respond quickly"""
        import time

        start = time.time()
        response = client.get("/health")
        duration = time.time() - start

        assert response.status_code == 200
        # Health check should respond in less than 100ms
        assert duration < 0.1

    def test_health_check_headers(self):
        """Test: Health check returns correct headers"""
        response = client.get("/health")

        assert response.status_code == 200
        assert "content-type" in response.headers
        assert "application/json" in response.headers["content-type"]
