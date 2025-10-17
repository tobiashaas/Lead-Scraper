"""
Integration Tests für Scraping API Endpoints
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.models import Source, ScrapingJob


@pytest.fixture
def create_test_source(db_session):
    """Create a test source in database"""
    source = Source(
        name="test_source",
        display_name="Test Source",
        url="https://test-source.com",
        source_type="web_scraper",
        is_active=True,
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)
    # Expunge to make it accessible from other sessions
    db_session.expunge(source)
    return source


@pytest.fixture
def sample_scraping_job_data():
    """Sample scraping job data"""
    return {
        "source_name": "test_source",
        "city": "Stuttgart",
        "industry": "IT-Services",
        "max_pages": 3,
        "use_tor": False,
        "use_ai": False,
    }


class TestScrapingEndpoints:
    """Test Suite für Scraping API Endpoints"""

    def test_create_scraping_job(
        self, create_test_source, sample_scraping_job_data, db_session, client, auth_headers
    ):
        """Test: Create a new scraping job"""
        # Debug: Check if source exists
        from app.database.models import Source

        sources = db_session.query(Source).all()
        print(f"Available sources: {[s.name for s in sources]}")

        response = client.post(
            "/api/v1/scraping/jobs", json=sample_scraping_job_data, headers=auth_headers
        )
        print(f"Sources in DB: {[s.name for s in sources]}")
        print(f"Source ID: {create_test_source.id}, Name: {create_test_source.name}")

        assert response.status_code == 201
        data = response.json()

        assert "id" in data
        assert data["city"] == sample_scraping_job_data["city"]
        assert data["industry"] == sample_scraping_job_data["industry"]
        assert data["status"] in ["pending", "running"]
        assert "created_at" in data

    def test_create_scraping_job_invalid_source(
        self, sample_scraping_job_data, client, auth_headers
    ):
        """Test: Creating job with invalid source should fail"""
        invalid_data = sample_scraping_job_data.copy()
        invalid_data["source_name"] = "non_existent_source"

        response = client.post("/api/v1/scraping/jobs", json=invalid_data, headers=auth_headers)

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_create_scraping_job_missing_fields(self, client, auth_headers):
        """Test: Creating job with missing required fields should fail"""
        incomplete_data = {
            "source_name": "test_source"
            # Missing city, industry
        }

        response = client.post("/api/v1/scraping/jobs", json=incomplete_data, headers=auth_headers)
        assert response.status_code == 422

    def test_list_scraping_jobs(self, client, auth_headers):
        """Test: List all scraping jobs"""
        response = client.get("/api/v1/scraping/jobs", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_list_scraping_jobs_with_pagination(self, client, auth_headers):
        """Test: List jobs with pagination"""
        response = client.get("/api/v1/scraping/jobs?skip=0&limit=10", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["skip"] == 0
        assert data["limit"] == 10

    def test_list_scraping_jobs_with_status_filter(self, client, auth_headers):
        """Test: Filter jobs by status"""
        response = client.get("/api/v1/scraping/jobs?status=completed", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # All returned jobs should have status 'completed'
        for job in data["items"]:
            assert job["status"] == "completed"

    def test_get_scraping_job_by_id(
        self, create_test_source, sample_scraping_job_data, client, auth_headers
    ):
        """Test: Get scraping job by ID"""
        # Create a job first
        create_response = client.post(
            "/api/v1/scraping/jobs", json=sample_scraping_job_data, headers=auth_headers
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        # Get the job
        response = client.get(f"/api/v1/scraping/jobs/{job_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == job_id
        assert data["city"] == sample_scraping_job_data["city"]

    def test_get_scraping_job_not_found(self, client, auth_headers):
        """Test: Get non-existent job returns 404"""
        response = client.get("/api/v1/scraping/jobs/99999", headers=auth_headers)

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_cancel_scraping_job(
        self, create_test_source, sample_scraping_job_data, client, auth_headers
    ):
        """Test: Cancel a running scraping job"""
        # Create a job
        create_response = client.post(
            "/api/v1/scraping/jobs", json=sample_scraping_job_data, headers=auth_headers
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        # Cancel the job
        response = client.delete(f"/api/v1/scraping/jobs/{job_id}", headers=auth_headers)

        assert response.status_code == 204

        # Verify job is cancelled
        get_response = client.get(f"/api/v1/scraping/jobs/{job_id}", headers=auth_headers)
        assert get_response.status_code == 200
        assert get_response.json()["status"] in ["cancelled", "failed"]

    def test_scraping_job_response_schema(
        self, create_test_source, sample_scraping_job_data, client, auth_headers
    ):
        """Test: Scraping job response has correct schema"""
        response = client.post(
            "/api/v1/scraping/jobs", json=sample_scraping_job_data, headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()

        # Required fields
        assert "id" in data
        assert "status" in data
        assert "city" in data
        assert "industry" in data
        assert "created_at" in data

        # Optional fields
        assert "job_name" in data
        assert "progress" in data or data.get("progress") is None
        assert "results_count" in data or data.get("results_count") is None

    def test_scraping_job_config(
        self, create_test_source, sample_scraping_job_data, client, auth_headers
    ):
        """Test: Scraping job stores config correctly"""
        response = client.post(
            "/api/v1/scraping/jobs", json=sample_scraping_job_data, headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()

        # Config should be stored
        if "config" in data:
            config = data["config"]
            assert config["use_tor"] == sample_scraping_job_data["use_tor"]
            assert config["use_ai"] == sample_scraping_job_data["use_ai"]

    def test_scraping_job_auto_naming(self, create_test_source, client, auth_headers):
        """Test: Job name is auto-generated if not provided"""
        job_data = {
            "source_name": "test_source",
            "city": "Stuttgart",
            "industry": "IT",
            "max_pages": 1,
            "use_tor": False,
            "use_ai": False,
            # No job_name provided
        }

        response = client.post("/api/v1/scraping/jobs", json=job_data, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()

        # Job name should be auto-generated
        assert "job_name" in data
        assert data["job_name"] is not None
        assert "test_source" in data["job_name"]
        assert "Stuttgart" in data["job_name"]

    def test_list_scraping_jobs_ordering(self, client, auth_headers):
        """Test: Jobs are ordered by creation date (newest first)"""
        response = client.get("/api/v1/scraping/jobs", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        if len(data["items"]) > 1:
            # Check that jobs are ordered by created_at descending
            for i in range(len(data["items"]) - 1):
                current = data["items"][i]["created_at"]
                next_item = data["items"][i + 1]["created_at"]
                assert current >= next_item

    def test_scraping_job_pagination_limits(self, client, auth_headers):
        """Test: Pagination limits are enforced"""
        # Test max limit
        response = client.get("/api/v1/scraping/jobs?limit=2000", headers=auth_headers)
        assert response.status_code == 422

        # Test negative skip
        response = client.get("/api/v1/scraping/jobs?skip=-1", headers=auth_headers)
        assert response.status_code == 422
