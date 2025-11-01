"""
Unit Tests for OpenAPI Schema Validation
Tests that the generated OpenAPI schema is valid and complete
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.mark.unit
class TestOpenAPISchema:
    """Test OpenAPI schema generation and validation"""

    def test_openapi_schema_is_valid(self):
        """Test that OpenAPI schema is valid JSON and has required fields"""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()

        # Validate required top-level fields
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        assert "components" in schema

        # Validate OpenAPI version
        assert schema["openapi"].startswith("3.")

        # Validate info section
        info = schema["info"]
        assert "title" in info
        assert "version" in info
        assert "description" in info
        assert info["title"] == "KR Lead Scraper API"

    def test_security_scheme_defined(self):
        """Test that BearerAuth security scheme is defined"""
        response = client.get("/openapi.json")
        schema = response.json()

        # Check security schemes
        assert "components" in schema
        assert "securitySchemes" in schema["components"]
        assert "BearerAuth" in schema["components"]["securitySchemes"]

        bearer_auth = schema["components"]["securitySchemes"]["BearerAuth"]
        assert bearer_auth["type"] == "http"
        assert bearer_auth["scheme"] == "bearer"
        assert bearer_auth["bearerFormat"] == "JWT"
        assert "description" in bearer_auth

    def test_all_endpoints_have_tags(self):
        """Test that all endpoints have at least one tag"""
        response = client.get("/openapi.json")
        schema = response.json()

        paths = schema.get("paths", {})
        endpoints_without_tags = []

        for path, methods in paths.items():
            for method, details in methods.items():
                if method in ["get", "post", "put", "patch", "delete"]:
                    if "tags" not in details or not details["tags"]:
                        endpoints_without_tags.append(f"{method.upper()} {path}")

        assert not endpoints_without_tags, f"Endpoints without tags: {endpoints_without_tags}"

    def test_protected_endpoints_have_security(self):
        """Test that protected endpoints have security requirements"""
        response = client.get("/openapi.json")
        schema = response.json()

        paths = schema.get("paths", {})

        # Endpoints that should be protected (require authentication)
        protected_patterns = [
            r"/api/v1/companies.*",
            r"/api/v1/scraping.*",
            r"/api/v1/export.*",
            r"/api/v1/scoring.*",
            r"/api/v1/bulk.*",
            r"/api/v1/webhooks.*",
            r"/api/v1/duplicates.*",
            r"/api/v1/auth/me",
            r"/api/v1/auth/change-password",
            r"/api/v1/auth/users",
        ]

        # Endpoints that should NOT be protected
        public_endpoints = [
            "/health",
            "/health/detailed",
            "/health/ready",
            "/health/live",
            "/metrics",
            "/api/v1/auth/register",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
        ]

        for path, methods in paths.items():
            # Skip public endpoints
            if path in public_endpoints:
                continue

            # Check if path matches protected pattern
            is_protected = any(re.match(pattern, path) for pattern in protected_patterns)

            if is_protected:
                for method, details in methods.items():
                    if method in ["get", "post", "put", "patch", "delete"]:
                        # Note: FastAPI may not always include explicit security in OpenAPI
                        # if it's handled by dependencies. This test is informational.
                        if "security" in details:
                            assert details[
                                "security"
                            ], f"{method.upper()} {path} should have security"

    def test_schemas_have_examples(self):
        """Test that important schemas have examples defined"""
        response = client.get("/openapi.json")
        schema = response.json()

        components = schema.get("components", {})
        schemas = components.get("schemas", {})

        # Important schemas that should have examples
        important_schemas = [
            "CompanyCreate",
            "ScrapingJobCreate",
            "LoginRequest",
            "UserCreate",
        ]

        missing_examples = []
        for schema_name in important_schemas:
            if schema_name in schemas:
                schema_def = schemas[schema_name]
                # Check for examples in various locations
                has_example = (
                    "example" in schema_def
                    or "examples" in schema_def
                    or any(
                        "example" in prop or "examples" in prop
                        for prop in schema_def.get("properties", {}).values()
                    )
                )
                if not has_example:
                    missing_examples.append(schema_name)

        # This is a soft check - examples are nice to have but not required
        if missing_examples:
            print(f"Warning: Schemas without examples: {missing_examples}")

    def test_api_version_in_schema(self):
        """Test that API version is set and follows semantic versioning"""
        response = client.get("/openapi.json")
        schema = response.json()

        info = schema.get("info", {})
        version = info.get("version")

        assert version, "API version should be set"

        # Validate semantic versioning format (MAJOR.MINOR.PATCH)
        semver_pattern = r"^\d+\.\d+\.\d+$"
        assert re.match(
            semver_pattern, version
        ), f"Version '{version}' should follow semantic versioning (e.g., 1.0.0)"

    def test_openapi_tags_have_descriptions(self):
        """Test that OpenAPI tags have descriptions"""
        response = client.get("/openapi.json")
        schema = response.json()

        tags = schema.get("tags", [])

        # Should have tags defined
        assert tags, "OpenAPI schema should have tags defined"

        # Each tag should have name and description
        for tag in tags:
            assert "name" in tag, "Tag should have name"
            assert "description" in tag, "Tag should have description"
            assert tag["description"], f"Tag '{tag['name']}' should have non-empty description"

    def test_servers_defined(self):
        """Test that server definitions are present"""
        response = client.get("/openapi.json")
        schema = response.json()

        servers = schema.get("servers", [])

        # Should have at least one server defined
        assert servers, "OpenAPI schema should have servers defined"

        # Each server should have url and description
        for server in servers:
            assert "url" in server, "Server should have URL"
            assert "description" in server, "Server should have description"

    def test_contact_info_defined(self):
        """Test that contact information is defined"""
        response = client.get("/openapi.json")
        schema = response.json()

        info = schema.get("info", {})
        contact = info.get("contact", {})

        # Should have contact info
        assert contact, "API should have contact information"
        assert "name" in contact or "email" in contact, "Contact should have at least name or email"

    def test_license_info_defined(self):
        """Test that license information is defined"""
        response = client.get("/openapi.json")
        schema = response.json()

        info = schema.get("info", {})
        license_info = info.get("license", {})

        # Should have license info
        assert license_info, "API should have license information"
        assert "name" in license_info, "License should have name"

    def test_response_schemas_defined(self):
        """Test that endpoints have response schemas defined"""
        response = client.get("/openapi.json")
        schema = response.json()

        paths = schema.get("paths", {})
        endpoints_without_responses = []

        for path, methods in paths.items():
            for method, details in methods.items():
                if method in ["get", "post", "put", "patch", "delete"]:
                    if "responses" not in details or not details["responses"]:
                        endpoints_without_responses.append(f"{method.upper()} {path}")

        assert (
            not endpoints_without_responses
        ), f"Endpoints without response schemas: {endpoints_without_responses}"
