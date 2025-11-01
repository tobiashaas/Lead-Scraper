"""Tests for scripts.load_testing.analyze_results."""
from __future__ import annotations

from pathlib import Path

import csv

import pytest

from scripts.load_testing.analyze_results import parse_locust_stats


@pytest.fixture()
def locust_stats_file(tmp_path: Path) -> Path:
    file_path = tmp_path / "sample_stats.csv"
    columns = [
        "Type",
        "Name",
        "Requests",
        "Failures",
        "Median Response Time",
        "Average Response Time",
        "Min Response Time",
        "Max Response Time",
        "95%",
        "99%",
        "Requests/s",
        "Average Content Size",
        "Method",
    ]
    with file_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerow(
            {
                "Type": "Request",
                "Name": "GET /companies",
                "Requests": "1200",
                "Failures": "12",
                "Median Response Time": "120",
                "Average Response Time": "150",
                "Min Response Time": "50",
                "Max Response Time": "450",
                "95%": "220",
                "99%": "360",
                "Requests/s": "40",
                "Average Content Size": "1024",
                "Method": "GET",
            }
        )
        writer.writerow(
            {
                "Type": "Request",
                "Name": "POST /companies",
                "Requests": "300",
                "Failures": "3",
                "Median Response Time": "180",
                "Average Response Time": "210",
                "Min Response Time": "80",
                "Max Response Time": "520",
                "95%": "320",
                "99%": "480",
                "Requests/s": "10",
                "Average Content Size": "2048",
                "Method": "POST",
            }
        )
        writer.writerow(
            {
                "Type": "Request",
                "Name": "DELETE /companies/{id}",
                "Requests": "60",
                "Failures": "0",
                "Median Response Time": "90",
                "Average Response Time": "100",
                "Min Response Time": "40",
                "Max Response Time": "220",
                "95%": "140",
                "99%": "180",
                "Requests/s": "5",
                "Average Content Size": "512",
                "Method": "DELETE",
            }
        )
        writer.writerow(
            {
                "Type": "Request",
                "Name": "_Total",
                "Requests": "1560",
                "Failures": "15",
                "Median Response Time": "135",
                "Average Response Time": "165",
                "Min Response Time": "40",
                "Max Response Time": "520",
                "95%": "260",
                "99%": "440",
                "Requests/s": "55",
                "Average Content Size": "1337",
                "Method": "",
            }
        )
    return file_path


def test_parse_locust_stats_uses_rps_fallback_for_duration(locust_stats_file: Path) -> None:
    stats = parse_locust_stats(locust_stats_file)

    # Requests/s sum = 40 + 10 + 5 = 55 -> duration = total_requests / sum_rps
    expected_duration = pytest.approx(1560 / 55, rel=1e-3)
    assert stats.duration_seconds == expected_duration
    assert stats.throughput_rpm == pytest.approx((1560 / expected_duration) * 60.0, rel=1e-6)
    assert stats.total_requests == 1560
    assert stats.total_failures == 15


def test_parse_locust_stats_handles_zero_rps(tmp_path: Path) -> None:
    file_path = tmp_path / "zero_rps.csv"
    columns = [
        "Type",
        "Name",
        "Requests",
        "Failures",
        "Requests/s",
    ]
    with file_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerow(
            {
                "Type": "Request",
                "Name": "GET /noop",
                "Requests": "100",
                "Failures": "0",
                "Requests/s": "0",
            }
        )
        writer.writerow(
            {
                "Type": "Request",
                "Name": "_Total",
                "Requests": "100",
                "Failures": "0",
                "Requests/s": "0",
            }
        )
    stats = parse_locust_stats(file_path)
    assert stats.duration_seconds == 0.0
    assert stats.throughput_rpm == 0.0
