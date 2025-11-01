"""Realistic mixed workload scenario for Locust."""
from __future__ import annotations

import random

from locust import FastHttpUser, between, task

from tests.load.config import (
    BASE_URL,
    SEARCH_TERMS,
    build_auth_headers,
    create_http_client,
    generate_random_company_data,
    get_auth_token,
    get_random_company_ids,
)


class MixedWorkloadUser(FastHttpUser):
    wait_time = between(0.5, 2.5)
    host = BASE_URL

    def on_start(self) -> None:
        token = get_auth_token(create_http_client())
        self.client.headers.update(build_auth_headers(token))

    @task(40)
    def read_operations(self) -> None:
        action = random.random()
        if action < 0.7:
            skip = random.randint(0, 500)
            self.client.get(f"/api/v1/companies?limit=50&skip={skip}")
        elif action < 0.9:
            ids = get_random_company_ids(1)
            if ids:
                self.client.get(f"/api/v1/companies/{ids[0]}")
        else:
            term = random.choice(SEARCH_TERMS)
            self.client.get(f"/api/v1/companies?search={term}")

    @task(10)
    def write_operations(self) -> None:
        action = random.random()
        if action < 0.5:
            payload = generate_random_company_data()
            self.client.post("/api/v1/companies", json=payload)
        elif action < 0.8:
            ids = get_random_company_ids(1)
            if ids:
                payload = generate_random_company_data()
                self.client.put(f"/api/v1/companies/{ids[0]}", json=payload)
        else:
            ids = get_random_company_ids(1)
            if ids:
                self.client.delete(f"/api/v1/companies/{ids[0]}")

    @task(5)
    def aggregation_operations(self) -> None:
        if random.random() < 0.5:
            self.client.get("/api/v1/companies/stats/overview")
        else:
            self.client.get("/api/v1/export/companies/stats")

    @task(1)
    def admin_operations(self) -> None:
        action = random.choice(["bulk", "score", "export"])
        if action == "bulk":
            ids = get_random_company_ids(random.randint(10, 30))
            payload = {
                "ids": ids,
                "updates": {
                    "lead_status": random.choice(["new", "contacted", "qualified", "won", "lost"]),
                },
            }
            self.client.post("/api/v1/bulk/companies/update", json=payload)
        elif action == "score":
            self.client.post("/api/v1/scoring/recalculate")
        else:
            limit = random.choice([500, 1000])
            self.client.get(f"/api/v1/export/companies/csv?limit={limit}")
