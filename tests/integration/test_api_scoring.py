"""Integration tests for Scoring API endpoints."""

from collections.abc import Callable

import pytest

from app.api import scoring as scoring_module
from app.api.scoring import map_quality_to_enum
from app.database.models import Company, LeadQuality, LeadStatus


def test_map_quality_to_enum_defaults_to_unknown() -> None:
    assert map_quality_to_enum("does-not-exist") == LeadQuality.UNKNOWN


@pytest.fixture
def create_company(db_session) -> Callable[..., Company]:
    """Create a company ready for scoring tests."""

    def _create(**overrides: object) -> Company:
        lead_status_override = overrides.get("lead_status", LeadStatus.NEW)
        if isinstance(lead_status_override, str):
            lead_status_override = LeadStatus[lead_status_override.upper()]

        lead_quality_override = overrides.get("lead_quality", LeadQuality.UNKNOWN)
        if isinstance(lead_quality_override, str):
            lead_quality_override = LeadQuality[lead_quality_override.upper()]

        company = Company(
            company_name=overrides.get("company_name", "Scoring Test Company"),
            email=overrides.get("email", "scoring@test.com"),
            phone=overrides.get("phone", "+49 711 123456"),
            website=overrides.get("website", "https://scoring.example.com"),
            street=overrides.get("street", "Score Street 1"),
            postal_code=overrides.get("postal_code", "70173"),
            city=overrides.get("city", "Stuttgart"),
            industry=overrides.get("industry", "Software Development"),
            team_size=overrides.get("team_size", 42),
            technologies=overrides.get("technologies", ["python", "aws", "kubernetes"]),
            directors=overrides.get("directors", ["Jane Doe"]),
            lead_status=lead_status_override,
            lead_quality=lead_quality_override,
        )
        db_session.add(company)
        db_session.commit()
        db_session.refresh(company)
        return company

    return _create


class TestScoringEndpoints:
    """Test suite for scoring operations."""

    def test_score_single_company_success(
        self, create_company, client, auth_headers, db_session
    ) -> None:
        company = create_company()

        response = client.post(f"/api/v1/scoring/companies/{company.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["company_id"] == company.id
        assert "score" in data and isinstance(data["score"], int | float)
        assert data["quality"] in {"hot", "warm", "cold", "low_quality"}
        assert "breakdown" in data
        assert "recommendations" in data

        db_session.refresh(company)
        assert company.lead_score == data["score"]
        expected_quality = map_quality_to_enum(data["quality"])
        if isinstance(company.lead_quality, str):
            assert company.lead_quality == expected_quality.value
        else:
            assert company.lead_quality == expected_quality

    def test_score_single_company_not_found(self, client, auth_headers) -> None:
        response = client.post("/api/v1/scoring/companies/99999", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Company not found"

    def test_score_multiple_companies_by_ids(
        self, create_company, client, auth_headers, db_session
    ) -> None:
        companies = [create_company(company_name=f"Bulk Score {idx}") for idx in range(3)]
        company_ids = [company.id for company in companies]

        response = client.post(
            "/api/v1/scoring/companies/bulk",
            json={"company_ids": company_ids},
            headers=auth_headers,
        )

        assert response.status_code == 200, response.json()
        data = response.json()
        assert data["total_scored"] == len(companies)
        assert isinstance(data["results"], list)
        assert {result["company_id"] for result in data["results"]} == set(company_ids)
        assert "stats" in data
        assert data["stats"]["total_scored"] == len(companies)

        for company in companies:
            db_session.refresh(company)
            assert company.lead_score is not None
            assert company.lead_quality is not None

    def test_get_scoring_stats(self, create_company, client, auth_headers) -> None:
        create_company()

        response = client.get("/api/v1/scoring/stats", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "total_companies" in data
        assert "average_score" in data
        assert "distribution_by_quality" in data
        assert "top_companies" in data and isinstance(data["top_companies"], list)
        assert "bottom_companies" in data and isinstance(data["bottom_companies"], list)

    def test_get_scoring_stats_handles_db_error(self, client, auth_headers, monkeypatch) -> None:
        def failing_select(*args, **kwargs):
            raise RuntimeError("db down")

        monkeypatch.setattr(scoring_module, "select", failing_select)

        response = client.get("/api/v1/scoring/stats", headers=auth_headers)

        assert response.status_code == 500
        assert "Stats failed" in response.json()["detail"]

    def test_score_single_company_handles_exception(
        self, create_company, client, auth_headers, monkeypatch
    ) -> None:
        company = create_company()

        def failing_score(*args, **kwargs):
            raise RuntimeError("scoring boom")

        monkeypatch.setattr(scoring_module, "score_company", failing_score)

        response = client.post(f"/api/v1/scoring/companies/{company.id}", headers=auth_headers)

        assert response.status_code == 500
        assert "Scoring failed" in response.json()["detail"]

    def test_score_multiple_companies_by_filters(
        self, create_company, client, auth_headers, db_session
    ) -> None:
        target = create_company(
            lead_status=LeadStatus.NEW,
            lead_quality=LeadQuality.UNKNOWN,
            company_name="Filtered Company",
        )
        create_company(
            lead_status=LeadStatus.CONTACTED,
            lead_quality=LeadQuality.A,
            company_name="Other Company",
        )

        response = client.post(
            "/api/v1/scoring/companies/bulk",
            params={
                "lead_status": LeadStatus.NEW.value,
                "lead_quality": LeadQuality.UNKNOWN.value,
                "limit": 5,
            },
            json={},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_scored"] >= 1
        scored_ids = {item["company_id"] for item in data["results"]}
        assert target.id in scored_ids

        db_session.refresh(target)
        assert target.lead_score is not None

    def test_score_multiple_companies_invalid_filter(self, client, auth_headers) -> None:
        response = client.post(
            "/api/v1/scoring/companies/bulk",
            params={"lead_status": "invalid"},
            json={},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid lead_status filter"

        response = client.post(
            "/api/v1/scoring/companies/bulk",
            params={"lead_quality": "invalid"},
            json={},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid lead_quality filter"

    def test_score_multiple_companies_handles_exception(
        self, create_company, client, auth_headers, monkeypatch
    ) -> None:
        company = create_company()

        def failing_score_lead(self, company_data):
            raise RuntimeError("bulk scoring failure")

        monkeypatch.setattr(scoring_module.LeadScorer, "score_lead", failing_score_lead)

        response = client.post(
            "/api/v1/scoring/companies/bulk",
            json={"company_ids": [company.id]},
            headers=auth_headers,
        )

        assert response.status_code == 500
        assert "Bulk scoring failed" in response.json()["detail"]
