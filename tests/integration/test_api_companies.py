"""
Integration Tests für Companies API Endpoints
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.models import Company, LeadStatus, LeadQuality


@pytest.fixture
def sample_company_data():
    """Sample company data for testing - unique per test"""
    import uuid

    unique_id = str(uuid.uuid4())[:8]
    return {
        "company_name": f"Test IT Solutions {unique_id} GmbH",
        "website": f"https://www.test-it-solutions-{unique_id}.de",
        "phone": "+49 711 123456",
        "email": f"info-{unique_id}@test-it-solutions.de",
        "address": "Teststraße 123",
        "postal_code": "70173",
        "city": f"Stuttgart-{unique_id}",
        "industry": "IT-Services",
        "description": "Test company for integration testing",
    }


@pytest.fixture
def create_test_company(db_session, sample_company_data):
    """Create a test company in database"""
    company = Company(**sample_company_data)
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


class TestCompaniesEndpoints:
    """Test Suite für Companies API Endpoints"""

    def test_list_companies_empty(self, client, auth_headers):
        """Test: List companies when database is empty"""
        response = client.get("/api/v1/companies/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_list_companies_with_pagination(self, client, auth_headers):
        """Test: List companies with pagination parameters"""
        response = client.get("/api/v1/companies/?skip=0&limit=10", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["skip"] == 0
        assert data["limit"] == 10

    def test_list_companies_with_city_filter(self, client, auth_headers):
        """Test: Filter companies by city"""
        response = client.get("/api/v1/companies/?city=Stuttgart", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # All returned companies should be from Stuttgart
        for company in data["items"]:
            if company.get("city"):
                assert "Stuttgart" in company["city"]

    def test_list_companies_with_industry_filter(self, client, auth_headers):
        """Test: Filter companies by industry"""
        response = client.get("/api/v1/companies/?industry=IT", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "items" in data

    def test_list_companies_with_search(self, client, auth_headers):
        """Test: Search companies by name/email/website"""
        response = client.get("/api/v1/companies/?search=test", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "items" in data

    def test_list_companies_pagination_limits(self, client, auth_headers):
        """Test: Pagination limits are enforced"""
        # Test max limit
        response = client.get("/api/v1/companies/?limit=2000", headers=auth_headers)
        assert response.status_code == 422  # Validation error

        # Test negative skip
        response = client.get("/api/v1/companies/?skip=-1", headers=auth_headers)
        assert response.status_code == 422

    def test_create_company(self, sample_company_data, client, auth_headers):
        """Test: Create a new company"""
        response = client.post("/api/v1/companies/", json=sample_company_data, headers=auth_headers)

        if response.status_code != 201:
            print(f"Response: {response.status_code} - {response.json()}")

        assert response.status_code == 201
        data = response.json()

        assert data["company_name"] == sample_company_data["company_name"]
        assert data["email"] == sample_company_data["email"]
        assert "id" in data
        assert "first_scraped_at" in data or "last_updated_at" in data

    def test_create_company_duplicate(self, sample_company_data, client, auth_headers):
        """Test: Creating duplicate company should fail"""
        # Create first company
        response1 = client.post(
            "/api/v1/companies/", json=sample_company_data, headers=auth_headers
        )
        assert response1.status_code == 201

        # Try to create duplicate
        response2 = client.post(
            "/api/v1/companies/", json=sample_company_data, headers=auth_headers
        )
        assert response2.status_code == 409  # Conflict

    def test_create_company_invalid_data(self, client, auth_headers):
        """Test: Creating company with invalid data should fail"""
        invalid_data = {"company_name": "", "city": "Stuttgart"}  # Empty name
        response = client.post("/api/v1/companies/", json=invalid_data, headers=auth_headers)
        assert response.status_code == 422

    def test_get_company_by_id(self, create_test_company, client, auth_headers):
        """Test: Get company by ID"""
        company = create_test_company

        response = client.get(f"/api/v1/companies/{company.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == company.id
        assert data["company_name"] == company.company_name

    def test_get_company_not_found(self, client, auth_headers):
        """Test: Get non-existent company returns 404"""
        response = client.get("/api/v1/companies/99999", headers=auth_headers)

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_update_company(self, create_test_company, client, auth_headers):
        """Test: Update company data"""
        company = create_test_company

        update_data = {"phone": "+49 711 999999", "lead_status": "contacted"}

        response = client.put(
            f"/api/v1/companies/{company.id}", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["phone"] == update_data["phone"]
        assert data["lead_status"] == update_data["lead_status"]

    def test_update_company_not_found(self, client, auth_headers):
        """Test: Update non-existent company returns 404"""
        update_data = {"phone": "+49 711 999999"}

        response = client.put("/api/v1/companies/99999", json=update_data, headers=auth_headers)
        assert response.status_code == 404

    def test_delete_company(self, create_test_company, client, auth_headers):
        """Test: Delete company (soft delete)"""
        company = create_test_company

        response = client.delete(f"/api/v1/companies/{company.id}", headers=auth_headers)

        assert response.status_code == 204

        # Verify company is soft-deleted
        get_response = client.get(f"/api/v1/companies/{company.id}", headers=auth_headers)
        assert get_response.status_code == 404 or get_response.json()["is_active"] == False

    def test_delete_company_not_found(self, client, auth_headers):
        """Test: Delete non-existent company returns 404"""
        response = client.delete("/api/v1/companies/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_list_companies_with_lead_status_filter(self, client, auth_headers):
        """Test: Filter companies by lead status"""
        response = client.get("/api/v1/companies/?lead_status=new", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        for company in data["items"]:
            if company.get("lead_status"):
                assert company["lead_status"] == "new"

    def test_list_companies_with_lead_quality_filter(self, client, auth_headers):
        """Test: Filter companies by lead quality"""
        response = client.get("/api/v1/companies/?lead_quality=a", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        for company in data["items"]:
            if company.get("lead_quality"):
                assert company["lead_quality"] == "a"

    def test_company_response_schema(self, create_test_company, client, auth_headers):
        """Test: Company response has correct schema"""
        company = create_test_company

        response = client.get(f"/api/v1/companies/{company.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "id" in data
        assert "company_name" in data
        assert "first_scraped_at" in data
        assert "last_updated_at" in data

        # Optional fields should be present (even if None)
        assert "email" in data
        assert "phone" in data
        assert "website" in data
