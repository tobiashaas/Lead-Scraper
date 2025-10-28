"""Integration tests for Export API endpoints."""

from collections.abc import Callable

import pytest
from fastapi import HTTPException

from app.api import export as export_module
from app.database.models import Company, LeadQuality, LeadStatus


@pytest.fixture
def create_companies(db_session) -> Callable[[int], list[Company]]:
    """Create companies with varying lead attributes for export tests."""

    def _create(count: int = 3) -> list[Company]:
        companies: list[Company] = []
        for idx in range(count):
            company = Company(
                company_name=f"Export Test Company {idx}",
                email=f"export{idx}@example.com",
                phone="+49 711 987654",
                website=f"https://export{idx}.example.com",
                street="Exportstraße 42",
                postal_code="70173",
                city="Stuttgart",
                industry="Consulting" if idx % 2 == 0 else "IT",
                lead_status=LeadStatus.CONTACTED if idx % 2 == 0 else LeadStatus.NEW,
                lead_quality=LeadQuality.A if idx % 2 == 0 else LeadQuality.B,
                lead_score=80 + idx,
            )
            db_session.add(company)
            companies.append(company)

        db_session.commit()
        for company in companies:
            db_session.refresh(company)
        return companies

    return _create


class TestExportEndpoints:
    """Test suite for export functionality."""

    def test_export_companies_csv_success(self, create_companies, client, auth_headers) -> None:
        companies = create_companies(2)

        response = client.get(
            "/api/v1/export/companies/csv",
            params={
                "lead_status": LeadStatus.CONTACTED.value,
                "lead_quality": LeadQuality.A.value,
                "limit": 10,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        body = response.text
        # Header and company rows should be present
        assert "Lead Status" in body
        assert companies[0].company_name in body

    def test_export_companies_csv_invalid_filter(self, client, auth_headers) -> None:
        response = client.get(
            "/api/v1/export/companies/csv",
            params={"lead_status": "invalid"},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "Invalid lead_status" in response.json()["detail"]

    def test_export_companies_csv_invalid_quality(self, client, auth_headers) -> None:
        response = client.get(
            "/api/v1/export/companies/csv",
            params={"lead_quality": "invalid"},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "Invalid lead_quality" in response.json()["detail"]

    def test_export_companies_csv_no_matches(self, create_companies, client, auth_headers) -> None:
        create_companies(2)

        response = client.get(
            "/api/v1/export/companies/csv",
            params={"lead_status": LeadStatus.REJECTED.value, "limit": 5},
            headers=auth_headers,
        )

        assert response.status_code == 200
        lines = [line for line in response.text.strip().splitlines() if line]
        assert len(lines) == 1  # only header row when no matches
        assert lines[0].startswith("ID,Name,City")

    def test_export_companies_csv_handles_exception(
        self, create_companies, client, auth_headers, monkeypatch
    ) -> None:
        create_companies(1)

        class FailingWriter:
            def writerow(self, *args, **kwargs):
                raise RuntimeError("csv failure")

        monkeypatch.setattr(export_module.csv, "writer", lambda *args, **kwargs: FailingWriter())

        response = client.get("/api/v1/export/companies/csv", headers=auth_headers)

        assert response.status_code == 500
        assert response.json()["detail"].startswith("CSV export failed")

    def test_export_companies_json_success(self, create_companies, client, auth_headers) -> None:
        create_companies(3)

        response = client.get(
            "/api/v1/export/companies/json",
            params={
                "lead_status": LeadStatus.NEW.value,
                "lead_quality": LeadQuality.B.value,
                "limit": 5,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert data["filters"]["lead_quality"] == LeadQuality.B.value
        assert any(company["lead_quality"] == LeadQuality.B.value for company in data["companies"])

    def test_export_companies_json_invalid_filter(self, client, auth_headers) -> None:
        response = client.get(
            "/api/v1/export/companies/json",
            params={"lead_quality": "invalid"},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "Invalid lead_quality" in response.json()["detail"]

    def test_export_companies_json_invalid_status(self, client, auth_headers) -> None:
        response = client.get(
            "/api/v1/export/companies/json",
            params={"lead_status": "invalid"},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid lead_status: invalid"

    def test_export_companies_json_limit(self, create_companies, client, auth_headers) -> None:
        create_companies(5)

        response = client.get(
            "/api/v1/export/companies/json",
            params={"limit": 2},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] <= 2
        assert len(data["companies"]) <= 2

    def test_export_companies_json_handles_exception(
        self, client, auth_headers, monkeypatch
    ) -> None:
        def failing_select(*args, **kwargs):
            raise RuntimeError("db down")

        monkeypatch.setattr(export_module, "select", failing_select)

        response = client.get("/api/v1/export/companies/json", headers=auth_headers)

        assert response.status_code == 500
        assert response.json()["detail"].startswith("JSON export failed")

    def test_export_companies_stats(self, create_companies, client, auth_headers) -> None:
        create_companies(4)

        response = client.get("/api/v1/export/companies/stats", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "total_companies" in data
        assert data["total_companies"] >= 1
        assert "by_lead_status" in data
        assert "by_lead_quality" in data
        assert isinstance(data["top_industries"], list)
        assert isinstance(data["top_cities"], list)

    def test_export_companies_stats_handles_exception(
        self, client, auth_headers, monkeypatch
    ) -> None:
        def failing_select(*args, **kwargs):
            raise RuntimeError("db down")

        monkeypatch.setattr(export_module, "select", failing_select)

        response = client.get("/api/v1/export/companies/stats", headers=auth_headers)

        assert response.status_code == 500
        assert response.json()["detail"].startswith("Stats export failed")

    def test_export_companies_stats_propagates_http_exception(
        self, client, auth_headers, monkeypatch
    ) -> None:
        def raising_select(*args, **kwargs):
            raise HTTPException(status_code=418, detail="teapot")

        monkeypatch.setattr(export_module, "select", raising_select)

        response = client.get("/api/v1/export/companies/stats", headers=auth_headers)

        assert response.status_code == 418
        assert response.json()["detail"] == "teapot"
