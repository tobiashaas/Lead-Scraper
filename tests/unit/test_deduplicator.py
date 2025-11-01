"""Unit tests for Deduplicator."""

from __future__ import annotations

from typing import Sequence
from unittest.mock import MagicMock, create_autospec

import pytest
from fuzzywuzzy import fuzz

from app.database.models import Company, DuplicateCandidate
from app.processors.deduplicator import Deduplicator


@pytest.fixture
def deduplicator() -> Deduplicator:
    return Deduplicator(
        name_threshold=80,
        address_threshold=70,
        phone_threshold=85,
        website_threshold=90,
        overall_threshold=75,
    )


@pytest.fixture
def company_a() -> Company:
    company = Company(
        id=1,
        company_name="Test Company GmbH",
        address="Main Street 1",
        phone="+49 711 123456",
        website="https://test-company.de",
        is_active=True,
        city="Stuttgart",
    )
    return company


@pytest.fixture
def company_b() -> Company:
    company = Company(
        id=2,
        company_name="Test Company GmbH",
        address="Main Street 1",
        phone="0711 123456",
        website="https://test-company.de",
        is_active=True,
        city="Stuttgart",
    )
    return company


def test_calculate_similarity(monkeypatch: pytest.MonkeyPatch, deduplicator: Deduplicator, company_a: Company, company_b: Company) -> None:
    monkeypatch.setattr(fuzz, "token_sort_ratio", lambda a, b: 90)
    monkeypatch.setattr(fuzz, "ratio", lambda a, b: 95)

    name_sim, address_sim, phone_sim, website_sim, overall_sim = deduplicator.calculate_similarity(company_a, company_b)

    assert name_sim == 90
    assert address_sim == 90
    assert phone_sim == 95
    assert website_sim == 95
    assert overall_sim == pytest.approx(92.0)


def test_is_duplicate_true(monkeypatch: pytest.MonkeyPatch, deduplicator: Deduplicator, company_a: Company, company_b: Company) -> None:
    monkeypatch.setattr(deduplicator, "calculate_similarity", lambda *_, **__: (90, 80, 90, 95, 88))

    assert deduplicator.is_duplicate(company_a, company_b) is True


def test_is_duplicate_false(monkeypatch: pytest.MonkeyPatch, deduplicator: Deduplicator, company_a: Company, company_b: Company) -> None:
    monkeypatch.setattr(deduplicator, "calculate_similarity", lambda *_, **__: (70, 60, 50, 40, 55))

    assert deduplicator.is_duplicate(company_a, company_b) is False


def _make_company(id_: int, name: str, city: str, address: str | None = None, phone: str | None = None, website: str | None = None) -> Company:
    company = Company(
        id=id_,
        company_name=name,
        city=city,
        is_active=True,
        address=address,
        phone=phone,
        website=website,
    )
    return company


def test_find_duplicates_filters_by_threshold(monkeypatch: pytest.MonkeyPatch, deduplicator: Deduplicator, company_a: Company) -> None:
    candidates = [
        _make_company(2, "Test Company GmbH", "Stuttgart"),
        _make_company(3, "Other Company", "Stuttgart"),
    ]

    db = MagicMock()
    db.query().filter().all.return_value = candidates

    def fake_calculate_similarity(base: Company, candidate: Company) -> Sequence[float]:
        return (0, 0, 0, 0, 85 if candidate.id == 2 else 60)

    monkeypatch.setattr(deduplicator, "calculate_similarity", fake_calculate_similarity)

    results = deduplicator.find_duplicates(db, company_a, limit=5)

    assert len(results) == 1
    assert results[0][0].id == 2
    assert results[0][1] == 85


def test_find_duplicates_limit(monkeypatch: pytest.MonkeyPatch, deduplicator: Deduplicator, company_a: Company) -> None:
    candidates = [_make_company(i, f"Candidate {i}", "Stuttgart") for i in range(2, 10)]
    db = MagicMock()
    db.query().filter().all.return_value = candidates

    monkeypatch.setattr(deduplicator, "calculate_similarity", lambda *_: (0, 0, 0, 0, 90))

    results = deduplicator.find_duplicates(db, company_a, limit=3)

    assert len(results) == 3
    assert all(score == 90 for _, score in results)


def test_create_duplicate_candidate_existing(deduplicator: Deduplicator, company_a: Company, company_b: Company) -> None:
    existing = DuplicateCandidate(company_a_id=company_a.id, company_b_id=company_b.id)

    db = MagicMock()
    db.query().filter().first.return_value = existing

    result = deduplicator.create_duplicate_candidate(db, company_a, company_b)

    assert result is existing
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_create_duplicate_candidate_new(monkeypatch: pytest.MonkeyPatch, deduplicator: Deduplicator, company_a: Company, company_b: Company) -> None:
    db = MagicMock()
    db.query().filter().first.return_value = None

    monkeypatch.setattr(deduplicator, "calculate_similarity", lambda *args, **kwargs: (90, 80, 70, 60, 85))

    candidate = deduplicator.create_duplicate_candidate(db, company_a, company_b)

    db.add.assert_called_once()
    db.commit.assert_called_once()
    assert candidate.company_a_id == company_a.id
    assert candidate.company_b_id == company_b.id
    assert candidate.overall_similarity == pytest.approx(0.85)


def test_merge_companies_prefers_primary(deduplicator: Deduplicator) -> None:
    primary = _make_company(1, "Primary", "Stuttgart", address="Main St", phone="123")
    duplicate = _make_company(2, "Duplicate", "Stuttgart", address=""); duplicate.phone = ""
    duplicate.email = "dup@example.com"
    duplicate.extra_data = {"sources": ["dup"]}

    db = MagicMock()

    result = deduplicator.merge_companies(db, primary, duplicate)

    assert result.email == "dup@example.com"
    assert duplicate.is_active is False
    assert duplicate.duplicate_of_id == primary.id
    db.commit.assert_called_once()


def test_merge_companies_merges_extra_sources(deduplicator: Deduplicator) -> None:
    primary = _make_company(1, "Primary", "Stuttgart")
    primary.extra_data = {"sources": ["primary"]}
    duplicate = _make_company(2, "Duplicate", "Stuttgart")
    duplicate.extra_data = {"sources": ["duplicate"]}

    db = MagicMock()

    deduplicator.merge_companies(db, primary, duplicate)

    assert primary.extra_data["sources"] == ["primary", "duplicate"]


def test_merge_companies_sets_inactive(deduplicator: Deduplicator) -> None:
    primary = _make_company(1, "Primary", "Stuttgart")
    duplicate = _make_company(2, "Duplicate", "Stuttgart")

    db = MagicMock()

    deduplicator.merge_companies(db, primary, duplicate)

    assert duplicate.is_active is False
    assert duplicate.is_duplicate is True


def test_scan_for_duplicates_processes_all(monkeypatch: pytest.MonkeyPatch, deduplicator: Deduplicator) -> None:
    companies = [_make_company(i, f"Company {i}", "Stuttgart") for i in range(1, 4)]

    db = MagicMock()
    db.query().filter().all.return_value = companies

    monkeypatch.setattr(deduplicator, "find_duplicates", lambda db, company, limit=5: [(company, 90)] if company.id == 1 else [])
    create_mock = MagicMock()
    monkeypatch.setattr(deduplicator, "create_duplicate_candidate", create_mock)

    result = deduplicator.scan_for_duplicates(db)

    assert result == 1
    create_mock.assert_called_once()


def test_find_duplicates_filters_inactive(monkeypatch: pytest.MonkeyPatch, deduplicator: Deduplicator, company_a: Company) -> None:
    inactive = _make_company(3, "Inactive", "Stuttgart")
    inactive.is_active = False
    active = _make_company(4, "Active", "Stuttgart")

    class QueryMock:
        def __init__(self, companies: list[Company]):
            self._companies = companies

        def filter(self, *args, **kwargs):
            active_companies = [c for c in self._companies if c.is_active]
            return QueryMock(active_companies)

        def all(self):
            return self._companies

    db = MagicMock()
    db.query.return_value = QueryMock([inactive, active])

    monkeypatch.setattr(deduplicator, "calculate_similarity", lambda *args, **kwargs: (0, 0, 0, 0, 90))

    results = deduplicator.find_duplicates(db, company_a)

    assert len(results) == 1
    assert results[0][0].id == active.id
