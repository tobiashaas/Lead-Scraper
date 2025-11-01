"""Primary Locust file defining the mixed workload scenario."""
from __future__ import annotations

import random

from locust import FastHttpUser, between, events, task

from tests.load.config import (
    BASE_URL,
    SEARCH_TERMS,
    build_auth_headers,
    create_http_client,
    ensure_seed_data,
    generate_random_company_data,
    get_auth_token,
    get_random_company_ids,
    refresh_company_pool,
)
from tests.load.prometheus_exporter import start_prometheus_exporter


class APIUser(FastHttpUser):
    wait_time = between(1, 3)
    host = BASE_URL

    def on_start(self) -> None:
        token = get_auth_token(create_http_client())
        self.client.headers.update(build_auth_headers(token))

    @task(10)
    def list_companies(self) -> None:
        skip = random.randint(0, 500)
        self.client.get(f"/api/v1/companies?limit=100&skip={skip}")

    @task(5)
    def search_companies(self) -> None:
        term = random.choice(SEARCH_TERMS)
        self.client.get(f"/api/v1/companies?search={term}")

    @task(3)
    def get_company_details(self) -> None:
        ids = get_random_company_ids(1)
        if ids:
            self.client.get(f"/api/v1/companies/{ids[0]}")

    @task(2)
    def export_stats(self) -> None:
        self.client.get("/api/v1/export/companies/stats")

    @task(2)
    def get_company_stats(self) -> None:
        self.client.get("/api/v1/companies/stats/overview")

    @task(1)
    def create_company(self) -> None:
        payload = generate_random_company_data()
        self.client.post("/api/v1/companies", json=payload)

    @task(1)
    def update_company(self) -> None:
        ids = get_random_company_ids(1)
        if not ids:
            return
        payload = generate_random_company_data()
        self.client.put(f"/api/v1/companies/{ids[0]}", json=payload)

    @task(1)
    def bulk_update(self) -> None:
        ids = get_random_company_ids(random.randint(10, 50))
        if not ids:
            return
        payload = {
            "ids": ids,
            "updates": {
                "lead_status": random.choice(["new", "contacted", "qualified", "won", "lost"]),
                "lead_quality": random.choice(["low", "medium", "high"]),
            },
        }
        self.client.post("/api/v1/bulk/companies/update", json=payload)

    @task(1)
    def export_csv(self) -> None:
        limit = random.choice([1000, 2000, 5000])
        self.client.get(f"/api/v1/export/companies/csv?limit={limit}")


@events.test_start.add_listener  # type: ignore[arg-type]
def on_test_start(environment, **_kwargs) -> None:  # type: ignore[annotation-unchecked]
    start_prometheus_exporter()
    client = create_http_client()
    token = get_auth_token(client)
    headers = build_auth_headers(token)
    ensure_seed_data(client, headers, count=1000)
    refresh_company_pool(client, headers)


@events.test_stop.add_listener  # type: ignore[arg-type]
def on_test_stop(environment, **_kwargs) -> None:  # type: ignore[annotation-unchecked]
    # Nothing to clean up for now, but hook retained for parity with plan.
    return
