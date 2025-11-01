"""Locust scenario emulating export-heavy workloads."""
from __future__ import annotations

import random

from locust import FastHttpUser, between, task

from tests.load.config import (
    BASE_URL,
    build_auth_headers,
    create_http_client,
    get_auth_token,
)


class ExportHeavyUser(FastHttpUser):
    wait_time = between(1, 4)
    host = BASE_URL

    def on_start(self) -> None:
        token = get_auth_token(create_http_client())
        self.client.headers.update(build_auth_headers(token))

    @task(5)
    def export_csv_large(self) -> None:
        limit = random.choice([1000, 5000, 10000])
        self.client.get(f"/api/v1/export/companies/csv?limit={limit}")

    @task(3)
    def export_json_large(self) -> None:
        limit = random.choice([500, 1000, 2000])
        self.client.get(f"/api/v1/export/companies/json?limit={limit}")

    @task(2)
    def export_stats(self) -> None:
        self.client.get("/api/v1/export/companies/stats")
