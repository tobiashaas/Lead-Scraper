"""Locust scenario focusing on bulk company operations."""
from __future__ import annotations

import random

from locust import FastHttpUser, between, task

from tests.load.config import (
    BASE_URL,
    build_auth_headers,
    create_http_client,
    generate_random_company_data,
    get_auth_token,
    get_random_company_ids,
)


class BulkOperationsUser(FastHttpUser):
    wait_time = between(2, 5)
    host = BASE_URL

    def on_start(self) -> None:
        token = get_auth_token(create_http_client())
        self.client.headers.update(build_auth_headers(token))

    @task(5)
    def bulk_update_companies(self) -> None:
        ids = get_random_company_ids(random.randint(50, 100))
        payload = {
            "ids": ids,
            "updates": {
                "lead_status": random.choice(["new", "contacted", "qualified", "won", "lost"]),
                "lead_quality": random.choice(["low", "medium", "high"]),
            },
        }
        self.client.post("/api/v1/bulk/companies/update", json=payload)

    @task(3)
    def bulk_status_change(self) -> None:
        ids = get_random_company_ids(random.randint(20, 50))
        payload = {
            "ids": ids,
            "status": random.choice(["active", "inactive"]),
        }
        self.client.post("/api/v1/bulk/companies/status", json=payload)

    @task(2)
    def bulk_delete(self) -> None:
        ids = get_random_company_ids(random.randint(10, 20))
        payload = {
            "ids": ids,
            "soft_delete": True,
        }
        self.client.post("/api/v1/bulk/companies/delete", json=payload)

    @task(1)
    def bulk_restore(self) -> None:
        ids = get_random_company_ids(random.randint(10, 20))
        payload = {"ids": ids}
        self.client.post("/api/v1/bulk/companies/restore", json=payload)
