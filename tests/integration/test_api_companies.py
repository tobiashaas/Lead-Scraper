"""Integration Tests für Companies API Endpoints."""



import pytest
from sqlalchemy.orm import Session

from app.database.models import Company, LeadQuality, LeadStatus

pytestmark = pytest.mark.integration


@pytest.fixture
def create_companies_batch(db_session):
    """Create multiple companies with varied attributes for filter testing."""

    def _create() -> dict[str, Company]:
        companies = {
            "berlin_consulting": Company(
                company_name="Acme Consulting Berlin",
                city="Berlin",
                industry="Consulting",
                lead_status=LeadStatus.QUALIFIED,
                lead_quality=LeadQuality.B,
                email="berlin@acme.example",
                is_active=True,
            ),
            "muenchen_it": Company(
                company_name="Acme IT München",
                city="München",
                industry="IT Services",
                lead_status=LeadStatus.NEW,
                lead_quality=LeadQuality.A,
                email="muenchen@acme.example",
                is_active=True,
            ),
            "inactive_company": Company(
                company_name="Inactive Company",
                city="Berlin",
                industry="Consulting",
                lead_status=LeadStatus.CONTACTED,
                lead_quality=LeadQuality.C,
                email="inactive@acme.example",
                is_active=False,
            ),
        }

        db_session.add_all(companies.values())
        db_session.commit()
        for company in companies.values():
            db_session.refresh(company)
        return companies

    return _create


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

    def test_list_companies_with_city_filter(self, create_companies_batch, client, auth_headers):
        """Test: Filter companies by city."""
        create_companies_batch()
        response = client.get("/api/v1/companies/?city=Berlin", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"]
        assert all("Berlin" in (company.get("city") or "") for company in data["items"])

    def test_list_companies_with_industry_filter(
        self, create_companies_batch, client, auth_headers
    ):
        """Test: Filter companies by industry."""
        create_companies_batch()
        response = client.get("/api/v1/companies/?industry=Consulting", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"]
        assert all("Consulting" in (company.get("industry") or "") for company in data["items"])

    def test_list_companies_with_search(self, create_companies_batch, client, auth_headers):
        """Test: Search companies by name/email/website."""
        create_companies_batch()
        response = client.get("/api/v1/companies/?search=Acme", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"]
        assert any("Acme" in company["company_name"] for company in data["items"])

    def test_list_companies_pagination_limits(self, client, auth_headers):
        """Test: Pagination limits are enforced"""
        # Test max limit
        response = client.get("/api/v1/companies/?limit=2000", headers=auth_headers)
        assert response.status_code == 422  # Validation error

    def test_get_stats(self, client, auth_headers, db_session, sample_company_data):
        """Test: Get statistics overview."""
        company = Company(**sample_company_data)
        company.lead_status = LeadStatus.NEW
        company.lead_quality = LeadQuality.A
        db_session.add(company)
        db_session.commit()

        response = client.get("/api/v1/companies/stats/overview", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total_companies"] >= 1
        assert "by_status" in data and isinstance(data["by_status"], dict)
        assert "by_quality" in data and isinstance(data["by_quality"], dict)
        assert "top_cities" in data and isinstance(data["top_cities"], list)
        first_city = data["top_cities"][0]
        assert "city" in first_city and "count" in first_city

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
        assert get_response.status_code == 404 or not get_response.json()["is_active"]

    def test_delete_company_not_found(self, client, auth_headers):
        """Test: Delete non-existent company returns 404"""
        response = client.delete("/api/v1/companies/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_list_companies_with_lead_status_filter(
        self, create_companies_batch, client, auth_headers
    ):
        """Test: Filter companies by lead status."""
        create_companies_batch()
        response = client.get("/api/v1/companies/?lead_status=qualified", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"]
        assert all(
            company["lead_status"] == LeadStatus.QUALIFIED.value for company in data["items"]
        )

    def test_list_companies_with_lead_quality_filter(
        self, create_companies_batch, client, auth_headers
    ):
        """Test: Filter companies by lead quality."""
        create_companies_batch()
        response = client.get("/api/v1/companies/?lead_quality=b", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"]
        assert all(company["lead_quality"] == LeadQuality.B.value for company in data["items"])

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

    def test_combined_filters(self, client, auth_headers, db_session: Session):
        """Test: Combined filters (city + industry + status)"""
        # Create test data
        companies = [
            Company(
                company_name=f"Test Company {i}",
                city="Berlin",
                industry="IT",
                lead_status=LeadStatus.QUALIFIED,
                lead_quality=LeadQuality.A,
                is_active=True,
            )
            for i in range(5)
        ]
        companies.append(
            Company(
                company_name="Other Company",
                city="Munich",  # Different city
                industry="IT",
                lead_status=LeadStatus.QUALIFIED,
                is_active=True,
            )
        )
        db_session.add_all(companies)
        db_session.commit()

        # Test combined filter
        response = client.get(
            "/api/v1/companies/?city=Berlin&industry=IT&lead_status=qualified", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5  # Only the Berlin IT companies
        assert all(
            c["city"] == "Berlin" and c["industry"] == "IT" and c["lead_status"] == "qualified"
            for c in data["items"]
        )

    def test_search_case_insensitive(self, client, auth_headers, db_session: Session):
        """Test: Search is case insensitive and handles special chars"""
        company = Company(
            company_name="Test & Company GmbH",
            email="info@test-company.de",
            city="Berlin",
            is_active=True,
        )
        db_session.add(company)
        db_session.commit()

        # Test case insensitivity
        for query in ["Test", "test", "TEST"]:
            response = client.get(f"/api/v1/companies/?search={query}", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) >= 1
            assert any(query.lower() in c["company_name"].lower() for c in data["items"])

        # Test special characters
        response = client.get(
            "/api/v1/companies/?search=Test%20%26%20Company", headers=auth_headers
        )
        assert response.status_code == 200
        assert any("Test & Company" in c["company_name"] for c in response.json()["items"])

    def test_pagination_beyond_total(self, client, auth_headers, db_session: Session):
        """Test: Pagination with skip > total returns empty list"""
        # Create some test companies
        companies = [
            Company(company_name=f"Test Company {i}", city="Berlin", is_active=True)
            for i in range(5)
        ]
        db_session.add_all(companies)
        db_session.commit()

        # Request page beyond total
        response = client.get("/api/v1/companies/?skip=100&limit=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 0

    def test_partial_update(self, create_test_company, client, auth_headers, db_session: Session):
        """Test: Partial update of company fields"""
        company = create_test_company

        # Store original values
        original_company_name = company.company_name
        original_email = company.email
        original_last_updated = company.last_updated_at

        # Update only phone
        update_data = {"phone": "+49 30 12345678"}
        response = client.put(
            f"/api/v1/companies/{company.id}", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Check only phone was updated in response
        assert data["phone"] == update_data["phone"]

        # Verify the update in the database
        db_session.refresh(company)
        assert company.phone == update_data["phone"]
        assert company.company_name == original_company_name  # Verify name wasn't changed
        assert company.email == original_email  # Verify email wasn't changed

        # Verify last_updated_at was updated
        assert company.last_updated_at > original_last_updated

    def test_set_fields_to_null(self, create_test_company, client, auth_headers):
        """Test: Setting optional fields to null"""
        company = create_test_company

        # Set optional fields to null
        update_data = {"phone": None, "email": None, "website": None}

        response = client.put(
            f"/api/v1/companies/{company.id}", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["phone"] is None
        assert data["email"] is None
        assert data["website"] is None

    def test_idempotent_delete(
        self, create_test_company, client, auth_headers, db_session: Session
    ):
        """Test: Deleting a company twice is idempotent"""
        company = create_test_company

        # First delete
        response1 = client.delete(f"/api/v1/companies/{company.id}", headers=auth_headers)
        assert response1.status_code == 204

        # Second delete should also succeed
        response2 = client.delete(f"/api/v1/companies/{company.id}", headers=auth_headers)
        assert response2.status_code == 204

        # Verify company is still soft-deleted
        company = db_session.query(Company).filter(Company.id == company.id).first()
        assert not company.is_active

    def test_stats_endpoint(self, client, auth_headers, db_session: Session):
        """Test: Stats endpoint returns correct distributions"""
        # Create test data
        test_data = [
            ("Company A", "Berlin", "IT", LeadStatus.QUALIFIED, LeadQuality.A),
            ("Company B", "Berlin", "IT", LeadStatus.QUALIFIED, LeadQuality.B),
            ("Company C", "Munich", "Finance", LeadStatus.CONTACTED, LeadQuality.C),
            ("Company D", "Hamburg", "IT", LeadStatus.NEW, LeadQuality.A),
            ("Company E", "Berlin", "Finance", LeadStatus.QUALIFIED, LeadQuality.B),
        ]

        for name, city, industry, status, quality in test_data:
            company = Company(
                company_name=name,
                city=city,
                industry=industry,
                lead_status=status,
                lead_quality=quality,
                is_active=True,
            )
            db_session.add(company)
        db_session.commit()

        # Get stats
        response = client.get("/api/v1/companies/stats/overview", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Check basic structure
        assert "total_companies" in data
        assert "by_status" in data
        assert "by_quality" in data
        assert "top_cities" in data

        # Check counts
        assert data["total_companies"] == 5

        # The API returns enum values as strings (e.g., "LeadStatus.QUALIFIED")
        # We need to handle different possible formats
        by_status_normalized = {}
        for key, value in data["by_status"].items():
            # Extract the enum value (e.g., "qualified" from "LeadStatus.QUALIFIED" or just "qualified")
            if "." in str(key):
                normalized_key = str(key).split(".")[-1].lower()
            else:
                normalized_key = str(key).lower()
            by_status_normalized[normalized_key] = value

        by_quality_normalized = {}
        for key, value in data["by_quality"].items():
            # Extract the enum value (e.g., "a" from "LeadQuality.A" or just "a")
            if "." in str(key):
                normalized_key = str(key).split(".")[-1].lower()
            else:
                normalized_key = str(key).lower()
            by_quality_normalized[normalized_key] = value

        assert by_status_normalized["qualified"] == 3
        assert by_quality_normalized["a"] == 2

        # Check top cities (limited to 10)
        assert len(data["top_cities"]) <= 10
        berlin = next((c for c in data["top_cities"] if c["city"] == "Berlin"), None)
        assert berlin["count"] == 3
