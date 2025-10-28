"""Integration tests for Bulk API endpoints."""

from collections.abc import Callable

import pytest

from app.api import bulk as bulk_module
from app.database.models import Company, LeadQuality, LeadStatus


@pytest.fixture
def create_companies(db_session) -> Callable[[int], list[Company]]:
    """Create and persist a number of companies for bulk operations."""

    def _create(count: int = 2) -> list[Company]:
        companies: list[Company] = []
        for index in range(count):
            company = Company(
                company_name=f"Bulk Test Company {index}",
                email=f"bulk{index}@example.com",
                phone="+49 711 123456",
                website=f"https://bulk{index}.example.com",
                street="Bulkstraße 1",
                postal_code="70173",
                city="Stuttgart",
                industry="Software",
            )
            db_session.add(company)
            companies.append(company)

        db_session.commit()
        for company in companies:
            db_session.refresh(company)
        return companies

    return _create


class TestBulkEndpoints:
    """Test suite for bulk company operations."""

    def test_bulk_update_companies_success(
        self, create_companies, client, auth_headers, db_session
    ) -> None:
        companies = create_companies(3)
        company_ids = [company.id for company in companies]
        payload = {
            "company_ids": company_ids,
            "updates": {
                "lead_status": LeadStatus.CONTACTED.value,
                "lead_quality": LeadQuality.A.value,
                "lead_score": 75.5,
                "industry": "Consulting",
            },
        }

        response = client.post("/api/v1/bulk/companies/update", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["updated_count"] == len(company_ids)
        assert data["failed_ids"] == []

        db_session.expire_all()
        updated = db_session.query(Company).filter(Company.id.in_(company_ids)).all()
        assert all(company.lead_status == LeadStatus.CONTACTED for company in updated)
        assert all(company.lead_quality == LeadQuality.A for company in updated)
        assert all(company.lead_score == pytest.approx(75.5) for company in updated)
        assert all(company.industry == "Consulting" for company in updated)

    def test_bulk_update_companies_invalid_fields(
        self, create_companies, client, auth_headers
    ) -> None:
        companies = create_companies(1)
        payload = {
            "company_ids": [companies[0].id],
            "updates": {"invalid_field": "value"},
        }

        response = client.post("/api/v1/bulk/companies/update", json=payload, headers=auth_headers)

        assert response.status_code == 400
        assert "Invalid update fields" in response.json()["detail"]

    def test_bulk_update_companies_with_missing_ids(
        self, create_companies, client, auth_headers
    ) -> None:
        companies = create_companies(1)
        existing_id = companies[0].id
        missing_id = existing_id + 999
        payload = {
            "company_ids": [existing_id, missing_id],
            "updates": {"industry": "Consulting"},
        }

        response = client.post("/api/v1/bulk/companies/update", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["updated_count"] == 1
        assert data["failed_ids"] == [missing_id]

    def test_bulk_update_companies_invalid_status(
        self, create_companies, client, auth_headers
    ) -> None:
        companies = create_companies(1)
        payload = {
            "company_ids": [companies[0].id],
            "updates": {"lead_status": "invalid"},
        }

        response = client.post("/api/v1/bulk/companies/update", json=payload, headers=auth_headers)

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid lead_status value"

    def test_bulk_update_companies_invalid_quality(
        self, create_companies, client, auth_headers
    ) -> None:
        companies = create_companies(1)
        payload = {
            "company_ids": [companies[0].id],
            "updates": {"lead_quality": "invalid"},
        }

        response = client.post("/api/v1/bulk/companies/update", json=payload, headers=auth_headers)

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid lead_quality value"

    def test_bulk_update_companies_no_ids(self, client, auth_headers) -> None:
        payload = {
            "company_ids": [],
            "updates": {"lead_status": LeadStatus.CONTACTED.value},
        }

        response = client.post("/api/v1/bulk/companies/update", json=payload, headers=auth_headers)

        assert response.status_code == 400
        assert response.json()["detail"] == "No company IDs provided"

    def test_bulk_delete_companies_soft(
        self, create_companies, client, auth_headers, db_session
    ) -> None:
        companies = create_companies(2)
        company_ids = [company.id for company in companies]
        payload = {"company_ids": company_ids, "soft_delete": True}

        response = client.post("/api/v1/bulk/companies/delete", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["deleted_count"] == len(company_ids)
        assert data["soft_delete"] is True

        db_session.expire_all()
        deleted = db_session.query(Company).filter(Company.id.in_(company_ids)).all()
        assert all(company.is_active is False for company in deleted)

    def test_bulk_delete_companies_hard(
        self, create_companies, client, auth_headers, db_session
    ) -> None:
        companies = create_companies(2)
        company_ids = [company.id for company in companies]
        payload = {"company_ids": company_ids, "soft_delete": False}

        response = client.post("/api/v1/bulk/companies/delete", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["deleted_count"] == len(company_ids)
        assert data["soft_delete"] is False

        db_session.expire_all()
        remaining = db_session.query(Company).filter(Company.id.in_(company_ids)).all()
        assert remaining == []

    def test_bulk_delete_companies_with_missing_ids(
        self, create_companies, client, auth_headers
    ) -> None:
        companies = create_companies(1)
        existing_id = companies[0].id
        missing_id = existing_id + 999
        payload = {"company_ids": [existing_id, missing_id], "soft_delete": True}

        response = client.post("/api/v1/bulk/companies/delete", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 1
        assert data["failed_ids"] == [missing_id]

    def test_bulk_delete_companies_no_ids(self, client, auth_headers) -> None:
        payload = {"company_ids": []}

        response = client.post("/api/v1/bulk/companies/delete", json=payload, headers=auth_headers)

        assert response.status_code == 400
        assert response.json()["detail"] == "No company IDs provided"

    def test_bulk_change_status_success(
        self, create_companies, client, auth_headers, db_session
    ) -> None:
        companies = create_companies(2)
        company_ids = [company.id for company in companies]
        payload = {
            "company_ids": company_ids,
            "lead_status": LeadStatus.QUALIFIED.value,
            "lead_quality": LeadQuality.B.value,
        }

        response = client.post("/api/v1/bulk/companies/status", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["updated_count"] == len(company_ids)
        assert data["changes"] == {
            "lead_status": LeadStatus.QUALIFIED.value,
            "lead_quality": LeadQuality.B.value,
        }

        db_session.expire_all()
        updated = db_session.query(Company).filter(Company.id.in_(company_ids)).all()
        assert all(company.lead_status == LeadStatus.QUALIFIED for company in updated)
        assert all(company.lead_quality == LeadQuality.B for company in updated)

    def test_bulk_change_status_missing_fields(
        self, create_companies, client, auth_headers
    ) -> None:
        companies = create_companies(1)
        payload = {"company_ids": [companies[0].id]}

        response = client.post("/api/v1/bulk/companies/status", json=payload, headers=auth_headers)

        assert response.status_code == 400
        assert (
            response.json()["detail"]
            == "At least one of lead_status or lead_quality must be provided"
        )

    def test_bulk_change_status_invalid_status(
        self, create_companies, client, auth_headers
    ) -> None:
        companies = create_companies(1)
        payload = {"company_ids": [companies[0].id], "lead_status": "invalid"}

        response = client.post("/api/v1/bulk/companies/status", json=payload, headers=auth_headers)

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid lead_status value"

    def test_bulk_change_status_invalid_quality(
        self, create_companies, client, auth_headers
    ) -> None:
        companies = create_companies(1)
        payload = {"company_ids": [companies[0].id], "lead_quality": "invalid"}

        response = client.post("/api/v1/bulk/companies/status", json=payload, headers=auth_headers)

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid lead_quality value"

    def test_bulk_change_status_no_ids(self, client, auth_headers) -> None:
        payload = {"company_ids": [], "lead_status": LeadStatus.CONTACTED.value}

        response = client.post("/api/v1/bulk/companies/status", json=payload, headers=auth_headers)

        assert response.status_code == 400
        assert response.json()["detail"] == "No company IDs provided"

    def test_bulk_restore_companies_success(
        self, create_companies, client, auth_headers, db_session
    ) -> None:
        companies = create_companies(2)
        company_ids = [company.id for company in companies]

        db_session.query(Company).filter(Company.id.in_(company_ids)).update(
            {"is_active": False}, synchronize_session=False
        )
        db_session.commit()

        response = client.post(
            "/api/v1/bulk/companies/restore", json=company_ids, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["restored_count"] == len(company_ids)

        db_session.expire_all()
        restored = db_session.query(Company).filter(Company.id.in_(company_ids)).all()
        assert all(company.is_active is True for company in restored)

    def test_bulk_restore_companies_no_ids(self, client, auth_headers) -> None:
        response = client.post("/api/v1/bulk/companies/restore", json=[], headers=auth_headers)

        assert response.status_code == 400
        assert response.json()["detail"] == "No company IDs provided"

    def test_bulk_restore_companies_only_restores_inactive(
        self, create_companies, client, auth_headers, db_session
    ) -> None:
        active_company, inactive_company = create_companies(2)
        db_session.query(Company).filter(Company.id == inactive_company.id).update(
            {"is_active": False}, synchronize_session=False
        )
        db_session.commit()

        response = client.post(
            "/api/v1/bulk/companies/restore",
            json=[active_company.id, inactive_company.id],
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["restored_count"] == 1

        db_session.expire_all()
        refreshed_active = db_session.get(Company, active_company.id)
        refreshed_inactive = db_session.get(Company, inactive_company.id)
        assert refreshed_active.is_active is True
        assert refreshed_inactive.is_active is True

    def test_bulk_update_companies_handles_db_error(
        self,
        create_companies,
        client,
        auth_headers,
        monkeypatch,
    ) -> None:
        companies = create_companies(1)
        payload = {
            "company_ids": [companies[0].id],
            "updates": {"industry": "Consulting"},
        }

        def failing_select(*args, **kwargs):
            raise RuntimeError("db failure")

        monkeypatch.setattr(bulk_module, "select", failing_select)

        response = client.post("/api/v1/bulk/companies/update", json=payload, headers=auth_headers)

        assert response.status_code == 500
        assert "Bulk update failed" in response.json()["detail"]

    def test_bulk_delete_companies_handles_db_error(
        self,
        create_companies,
        client,
        auth_headers,
        monkeypatch,
    ) -> None:
        companies = create_companies(1)
        payload = {"company_ids": [companies[0].id], "soft_delete": True}

        def failing_select(*args, **kwargs):
            raise RuntimeError("db failure")

        monkeypatch.setattr(bulk_module, "select", failing_select)

        response = client.post("/api/v1/bulk/companies/delete", json=payload, headers=auth_headers)

        assert response.status_code == 500
        assert "Bulk delete failed" in response.json()["detail"]

    def test_bulk_change_status_handles_db_error(
        self,
        create_companies,
        client,
        auth_headers,
        monkeypatch,
    ) -> None:
        companies = create_companies(1)
        payload = {
            "company_ids": [companies[0].id],
            "lead_status": LeadStatus.CONTACTED.value,
        }

        def failing_select(*args, **kwargs):
            raise RuntimeError("db failure")

        monkeypatch.setattr(bulk_module, "select", failing_select)

        response = client.post("/api/v1/bulk/companies/status", json=payload, headers=auth_headers)

        assert response.status_code == 500
        assert "Bulk status change failed" in response.json()["detail"]

    def test_bulk_restore_companies_handles_db_error(
        self,
        create_companies,
        client,
        auth_headers,
        db_session,
        monkeypatch,
    ) -> None:
        companies = create_companies(1)
        company_ids = [company.id for company in companies]

        db_session.query(Company).filter(Company.id.in_(company_ids)).update(
            {"is_active": False}, synchronize_session=False
        )
        db_session.commit()

        def failing_update(*args, **kwargs):
            raise RuntimeError("db failure")

        monkeypatch.setattr(bulk_module, "update", failing_update)

        response = client.post(
            "/api/v1/bulk/companies/restore", json=company_ids, headers=auth_headers
        )

        assert response.status_code == 500
        assert "Bulk restore failed" in response.json()["detail"]
