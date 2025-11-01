"""Shared configuration and utilities for Locust load testing."""
from __future__ import annotations

import json
import os
import random
from functools import lru_cache
from typing import Any, Optional

import httpx
from faker import Faker

BASE_URL = os.getenv("LOAD_TEST_BASE_URL", "http://localhost:8000")
TEST_USER_CREDENTIALS = {
    "email": os.getenv("LOAD_TEST_USER_EMAIL", "loadtest@example.com"),
    "password": os.getenv("LOAD_TEST_USER_PASSWORD", "loadtest-password"),
}
COMPANY_IDS_POOL_SIZE = int(os.getenv("LOAD_TEST_COMPANY_POOL_SIZE", "200"))
PERFORMANCE_TARGETS = {
    "p95_latency_ms": 200,
    "error_rate_pct": 1.0,
    "throughput_rpm": 1000,
}
SEARCH_TERMS = [
    "GmbH",
    "Software",
    "IT",
    "Consulting",
    "Stuttgart",
    "Marketing",
    "B2B",
]

faker = Faker("de_DE")
_company_pool: list[int] = []
_token_cache: Optional[str] = None


@lru_cache(maxsize=1)
def create_http_client(base_url: Optional[str] = None) -> httpx.Client:
    """Return a shared HTTP client for load testing helpers."""
    url = base_url or BASE_URL
    return httpx.Client(base_url=url, timeout=30.0)


def get_auth_token(client: httpx.Client, force_refresh: bool = False) -> str:
    """Authenticate the load-testing user and return a bearer token."""
    global _token_cache
    if _token_cache and not force_refresh:
        return _token_cache

    response = client.post("/api/v1/auth/login", json=TEST_USER_CREDENTIALS)
    response.raise_for_status()
    data = response.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Authentication response did not include access_token")
    _token_cache = token
    return token


def build_auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def refresh_company_pool(
    client: httpx.Client,
    headers: dict[str, str],
    pool_size: int = COMPANY_IDS_POOL_SIZE,
) -> None:
    """Populate the global company ID pool for random access."""
    ids: list[int] = []
    page = 0
    while len(ids) < pool_size:
        response = client.get(
            "/api/v1/companies",
            headers=headers,
            params={"limit": 100, "skip": page * 100},
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("items") or payload.get("data") or []
        if not items:
            break
        ids.extend(item["id"] for item in items if "id" in item)
        page += 1
    global _company_pool
    _company_pool = ids[:pool_size]


def get_random_company_ids(count: int = 10) -> list[int]:
    if not _company_pool:
        raise RuntimeError(
            "Company pool has not been initialised. Call refresh_company_pool first."
        )
    return random.sample(_company_pool, min(count, len(_company_pool)))


def seed_test_data(
    client: httpx.Client,
    headers: dict[str, str],
    count: int = 1000,
) -> None:
    """Create synthetic company data for load testing."""
    payload = [generate_random_company_data() for _ in range(count)]
    response = client.post(
        "/api/v1/bulk/companies/create",
        headers=headers,
        json={"companies": payload},
    )
    if response.status_code == 404:
        for company in payload:
            single_response = client.post(
                "/api/v1/companies",
                headers=headers,
                json=company,
            )
            single_response.raise_for_status()
    else:
        response.raise_for_status()


def generate_random_company_data() -> dict[str, Any]:
    company_name = faker.company()
    return {
        "name": company_name,
        "email": faker.company_email(domain="example.com"),
        "website": faker.url(),
        "phone": faker.phone_number(),
        "address": faker.street_address(),
        "city": faker.city(),
        "zipcode": faker.postcode(),
        "country": "Deutschland",
        "lead_status": random.choice(["new", "contacted", "qualified", "won", "lost"]),
        "lead_quality": random.choice(["low", "medium", "high"]),
        "industry": random.choice(
            [
                "Software",
                "Beratung",
                "Marketing",
                "E-Commerce",
                "Finanzen",
                "Maschinenbau",
            ]
        ),
        "notes": faker.text(max_nb_chars=200),
        "metadata": {"source": "load-test", "score": random.randint(10, 90)},
    }


def ensure_seed_data(client: httpx.Client, headers: dict[str, str], count: int = 1000) -> None:
    if not _company_pool:
        seed_test_data(client, headers, count=count)
        refresh_company_pool(client, headers)


def dump_performance_targets(path: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(PERFORMANCE_TARGETS, handle, indent=2)


def reset_state() -> None:
    global _company_pool, _token_cache
    _company_pool = []
    _token_cache = None
    create_http_client.cache_clear()


__all__ = [
    "BASE_URL",
    "PERFORMANCE_TARGETS",
    "SEARCH_TERMS",
    "build_auth_headers",
    "create_http_client",
    "dump_performance_targets",
    "ensure_seed_data",
    "generate_random_company_data",
    "get_auth_token",
    "get_random_company_ids",
    "refresh_company_pool",
    "reset_state",
    "seed_test_data",
]
