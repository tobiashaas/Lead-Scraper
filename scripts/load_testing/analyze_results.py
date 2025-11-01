"""Analyze Locust load test results and produce summary reports."""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

DEFAULT_TARGETS = {
    "p95_latency_ms": 200.0,
    "error_rate_pct": 1.0,
    "throughput_rpm": 1000.0,
}

DEFAULT_OUTPUT_DIR = Path("data/load_tests")
DEFAULT_REPORT_FILE = DEFAULT_OUTPUT_DIR / "analysis_report.md"


@dataclass(slots=True)
class EndpointStats:
    name: str
    method: str
    requests: int
    failures: int
    median_ms: float
    p95_ms: float
    p99_ms: float
    avg_ms: float
    min_ms: float
    max_ms: float
    rps: float
    avg_size: float

    @property
    def error_rate_pct(self) -> float:
        if self.requests == 0:
            return 0.0
        return (self.failures / self.requests) * 100.0


@dataclass(slots=True)
class TestStats:
    endpoints: list[EndpointStats]
    total_requests: int
    total_failures: int
    duration_seconds: float

    @property
    def error_rate_pct(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.total_failures / self.total_requests) * 100.0

    @property
    def throughput_rps(self) -> float:
        if self.duration_seconds <= 0:
            return 0.0
        return self.total_requests / self.duration_seconds

    @property
    def throughput_rpm(self) -> float:
        return self.throughput_rps * 60.0


def parse_locust_stats(csv_file: Path) -> TestStats:
    """Parse Locust statistics CSV into structured data."""
    endpoints: list[EndpointStats] = []
    total_requests = 0
    total_failures = 0
    test_duration_seconds: Optional[float] = None

    with csv_file.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("Name") in {"Total", "_Total"}:
                total_requests = int(float(row.get("Requests", "0")))
                total_failures = int(float(row.get("Failures", "0")))
                continue

            if row.get("Type") not in {"HTTP", "Request"}:
                continue

            endpoint = EndpointStats(
                name=row.get("Name", "unknown"),
                method=row.get("Method", row.get("Type", "GET")),
                requests=int(float(row.get("Requests", "0"))),
                failures=int(float(row.get("Failures", "0"))),
                median_ms=float(row.get("Median Response Time", "0")),
                p95_ms=float(row.get("95%", row.get("95%ile", "0"))),
                p99_ms=float(row.get("99%", row.get("99%ile", "0"))),
                avg_ms=float(row.get("Average Response Time", "0")),
                min_ms=float(row.get("Min Response Time", "0")),
                max_ms=float(row.get("Max Response Time", "0")),
                rps=float(row.get("Requests/s", "0")),
                avg_size=float(row.get("Average Content Size", "0")),
            )
            endpoints.append(endpoint)

    if test_duration_seconds is None:
        # Fallback: estimate using sum of requests / average RPS
        total_rps = sum(ep.rps for ep in endpoints)
        test_duration_seconds = total_requests / total_rps if total_rps else 0.0

    return TestStats(
        endpoints=endpoints,
        total_requests=total_requests,
        total_failures=total_failures,
        duration_seconds=test_duration_seconds or 0.0,
    )


def calculate_performance_score(stats: TestStats, targets: dict[str, float]) -> dict[str, Any]:
    """Calculate overall performance score compared to targets."""
    scores: dict[str, tuple[float, bool]] = {}

    # Throughput score
    throughput_target = targets.get("throughput_rpm", DEFAULT_TARGETS["throughput_rpm"])
    throughput = stats.throughput_rpm
    throughput_ratio = min(throughput / throughput_target, 1.0)
    scores["throughput_rpm"] = (throughput_ratio * 100.0, throughput >= throughput_target)

    # Error rate score
    error_target = targets.get("error_rate_pct", DEFAULT_TARGETS["error_rate_pct"])
    error_rate = stats.error_rate_pct
    error_score = max(0.0, 100.0 - min(error_rate / error_target, 1.0) * 100.0)
    scores["error_rate_pct"] = (error_score, error_rate <= error_target)

    # Latency score (p95 average)
    latency_target = targets.get("p95_latency_ms", DEFAULT_TARGETS["p95_latency_ms"])
    if stats.endpoints:
        avg_p95 = sum(ep.p95_ms for ep in stats.endpoints if ep.requests) / max(
            1, sum(1 for ep in stats.endpoints if ep.requests)
        )
    else:
        avg_p95 = latency_target
    latency_ratio = min(latency_target / avg_p95 if avg_p95 else 1.0, 1.0)
    scores["p95_latency_ms"] = (latency_ratio * 100.0, avg_p95 <= latency_target)

    overall_score = sum(value for value, _ in scores.values()) / max(len(scores), 1)
    passed = all(flag for _, flag in scores.values())

    return {
        "score": round(overall_score, 2),
        "passed": passed,
        "metrics": {
            metric: {"score": round(value, 2), "passed": passed_flag}
            for metric, (value, passed_flag) in scores.items()
        },
        "throughput_rpm": round(throughput, 2),
        "error_rate_pct": round(error_rate, 3),
        "avg_p95_latency_ms": round(avg_p95, 2),
    }


def identify_bottlenecks(stats: TestStats) -> list[dict[str, Any]]:
    bottlenecks: list[dict[str, Any]] = []
    for endpoint in stats.endpoints:
        if endpoint.requests == 0:
            continue
        if endpoint.p95_ms > 500 or endpoint.error_rate_pct > 1.0:
            bottlenecks.append(
                {
                    "endpoint": endpoint.name,
                    "method": endpoint.method,
                    "p95_ms": endpoint.p95_ms,
                    "error_rate_pct": endpoint.error_rate_pct,
                    "requests": endpoint.requests,
                }
            )
    # Sort by severity (highest latency first, then error rate)
    bottlenecks.sort(key=lambda item: (item["p95_ms"], item["error_rate_pct"]), reverse=True)
    return bottlenecks


def compare_with_baseline(current: TestStats, baseline: TestStats) -> dict[str, Any]:
    return {
        "throughput_delta_rpm": round(current.throughput_rpm - baseline.throughput_rpm, 2),
        "error_rate_delta_pct": round(current.error_rate_pct - baseline.error_rate_pct, 3),
    }


def generate_markdown_report(
    stats: TestStats,
    score: dict[str, Any],
    bottlenecks: list[dict[str, Any]],
    baseline_comparison: Optional[dict[str, Any]] = None,
    scenario_name: Optional[str] = None,
) -> str:
    lines: list[str] = []
    lines.append("# Load Test Analysis Report\n")
    if scenario_name:
        lines.append(f"**Scenario:** `{scenario_name}`\n")
    lines.append(f"**Total Requests:** {stats.total_requests}\n")
    lines.append(f"**Error Rate:** {stats.error_rate_pct:.2f}%\n")
    lines.append(f"**Throughput:** {stats.throughput_rpm:.2f} rpm\n")
    lines.append(f"**Overall Score:** {score['score']} ({'PASS' if score['passed'] else 'FAIL'})\n")

    lines.append("\n## Metric Scores\n")
    lines.append("| Metric | Score | Target Met |\n")
    lines.append("| --- | --- | --- |\n")
    for metric, details in score["metrics"].items():
        lines.append(
            f"| {metric} | {details['score']:.2f} | {'✅' if details['passed'] else '❌'} |\n"
        )

    if baseline_comparison:
        lines.append("\n## Baseline Comparison\n")
        lines.append(f"- Throughput Δ: {baseline_comparison['throughput_delta_rpm']:+.2f} rpm\n")
        lines.append(f"- Error Rate Δ: {baseline_comparison['error_rate_delta_pct']:+.2f}%\n")

    lines.append("\n## Endpoint Metrics\n")
    lines.append(
        "| Endpoint | Method | Requests | Failures | Error % | p50 ms | p95 ms | p99 ms | RPS |\n"
    )
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |\n")
    for endpoint in stats.endpoints:
        lines.append(
            "| {name} | {method} | {req} | {fail} | {err:.2f} | {p50:.1f} | {p95:.1f} | {p99:.1f} | {rps:.2f} |\n".format(
                name=endpoint.name,
                method=endpoint.method,
                req=endpoint.requests,
                fail=endpoint.failures,
                err=endpoint.error_rate_pct,
                p50=endpoint.median_ms,
                p95=endpoint.p95_ms,
                p99=endpoint.p99_ms,
                rps=endpoint.rps,
            )
        )

    if bottlenecks:
        lines.append("\n## Identified Bottlenecks\n")
        for item in bottlenecks:
            lines.append(
                "- `{method} {endpoint}` — p95: {p95:.1f} ms, error rate: {err:.2f}%, requests: {req}\n".format(
                    method=item["method"],
                    endpoint=item["endpoint"],
                    p95=item["p95_ms"],
                    err=item["error_rate_pct"],
                    req=item["requests"],
                )
            )
    else:
        lines.append("\n## Identified Bottlenecks\n")
        lines.append("No significant bottlenecks detected. ✅\n")

    return "".join(lines)


def load_targets(targets_path: Optional[Path]) -> dict[str, float]:
    if targets_path and targets_path.exists():
        with targets_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    return DEFAULT_TARGETS.copy()


def load_baseline(baseline_path: Optional[Path]) -> Optional[TestStats]:
    if baseline_path and baseline_path.exists():
        return parse_locust_stats(baseline_path)
    return None


def determine_scenario_name(stats_csv: Path) -> str:
    return stats_csv.stem.replace("_stats", "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Locust load test results")
    parser.add_argument(
        "--stats-csv", required=True, type=Path, help="Path to Locust stats CSV file"
    )
    parser.add_argument(
        "--output",
        choices={"markdown", "json", "both"},
        default="markdown",
        help="Output format",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Optional baseline stats CSV for comparison",
    )
    parser.add_argument(
        "--targets",
        type=Path,
        help="Optional JSON file with performance targets",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit with status 1 if performance regresses relative to baseline",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_FILE,
        help="Path to write markdown report",
    )

    args = parser.parse_args()

    stats = parse_locust_stats(args.stats_csv)
    targets = load_targets(args.targets)
    score = calculate_performance_score(stats, targets)
    bottlenecks = identify_bottlenecks(stats)

    baseline_stats: Optional[TestStats] = None
    baseline_comparison: Optional[dict[str, Any]] = None
    if args.baseline:
        baseline_stats = parse_locust_stats(args.baseline)
        baseline_comparison = compare_with_baseline(stats, baseline_stats)

    scenario_name = determine_scenario_name(args.stats_csv)
    markdown_report = generate_markdown_report(
        stats=stats,
        score=score,
        bottlenecks=bottlenecks,
        baseline_comparison=baseline_comparison,
        scenario_name=scenario_name,
    )

    if args.output in {"markdown", "both"}:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(markdown_report, encoding="utf-8")

    if args.output in {"json", "both"}:
        summary = {
            "scenario": scenario_name,
            "score": score,
            "bottlenecks": bottlenecks,
            "baseline_comparison": baseline_comparison,
        }
        print(json.dumps(summary, indent=2))

    should_fail = False
    if not score["passed"]:
        should_fail = True

    if args.fail_on_regression and baseline_comparison:
        throughput_delta = baseline_comparison["throughput_delta_rpm"]
        error_delta = baseline_comparison["error_rate_delta_pct"]
        if throughput_delta < 0 or error_delta > 0:
            should_fail = True

    if should_fail:
        raise SystemExit("Performance criteria not met")


if __name__ == "__main__":
    main()
