"""Profile FastAPI endpoints for CPU, memory, and database behaviour."""
from __future__ import annotations

import argparse
import asyncio
import cProfile
import io
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import httpx
from memory_profiler import memory_usage
from sqlalchemy import text
from sqlalchemy.engine import Engine, create_engine

from app.core.config import settings

DEFAULT_BASE_URL = os.getenv(
    "PROFILE_BASE_URL",
    getattr(settings, "api_base_url", None)
    or f"http://{settings.api_host}:{settings.api_port}",
)
DEFAULT_OUTPUT_DIR = Path("data/profiling")
DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def _exercise_endpoint(
    endpoint: str,
    method: str,
    iterations: int,
    base_url: str,
    payload: Optional[Dict[str, Any]] = None,
) -> List[float]:
    """Execute the endpoint multiple times and record response durations."""

    url = base_url.rstrip("/") + "/" + endpoint.lstrip("/")
    durations: List[float] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for _ in range(iterations):
            start = time.perf_counter()
            response = await client.request(method.upper(), url, json=payload)
            response.raise_for_status()
            durations.append((time.perf_counter() - start) * 1000)
    return durations


def _safe_name(endpoint: str) -> str:
    cleaned = endpoint.strip("/").replace("/", "_").replace("?", "_")
    return cleaned or "root"


def profile_endpoint_cpu(
    endpoint: str,
    method: str,
    iterations: int,
    base_url: str,
    output_dir: Path,
    payload: Optional[Dict[str, Any]] = None,
) -> Path:
    """Profile CPU usage using cProfile and save stats file."""

    profiler = cProfile.Profile()

    async def runner() -> None:
        await _exercise_endpoint(endpoint, method, iterations, base_url, payload)

    profiler.enable()
    asyncio.run(runner())
    profiler.disable()

    output_path = output_dir / f"{_safe_name(endpoint)}_cpu.prof"
    profiler.dump_stats(str(output_path))

    readable_stats = io.StringIO()
    stats = cProfile.Stats(profiler, stream=readable_stats).sort_stats("cumulative")
    stats.print_stats(30)
    (output_dir / f"{_safe_name(endpoint)}_cpu.txt").write_text(readable_stats.getvalue(), encoding="utf-8")
    return output_path


def profile_endpoint_memory(
    endpoint: str,
    method: str,
    iterations: int,
    base_url: str,
    output_dir: Path,
    payload: Optional[Dict[str, Any]] = None,
) -> Path:
    """Profile memory usage using memory_profiler."""

    async def runner() -> None:
        await _exercise_endpoint(endpoint, method, iterations, base_url, payload)

    def _run() -> None:
        asyncio.run(runner())

    usage = memory_usage((_run, ()), interval=0.1, retval=False)
    peak = max(usage) if usage else 0.0
    report_path = output_dir / f"{_safe_name(endpoint)}_memory.txt"
    report_path.write_text(
        "Peak memory usage: {:.2f} MiB\nSamples: {}".format(peak, len(usage)),
        encoding="utf-8",
    )
    return report_path


def profile_with_pyspy(
    endpoint: str,
    method: str,
    duration: int,
    base_url: str,
    output_dir: Path,
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[Path]:
    """Capture a flamegraph using py-spy by spawning a helper process."""

    if not shutil.which("py-spy"):
        print("py-spy not installed. Skipping py-spy profiling.", file=sys.stderr)
        return None

    helper_script = f"""
import asyncio
import json
import os
import time

import httpx

async def main():
    url = "{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    payload = {payload if payload is not None else 'None'}
    end = time.time() + {duration}
    async with httpx.AsyncClient(timeout=30.0) as client:
        while time.time() < end:
            await client.request("{method.upper()}", url, json=payload)

asyncio.run(main())
"""
    
    with tempfile.NamedTemporaryFile(mode="w", suffix="_pyspy_runner.py", delete=False) as tmp:
        tmp.write(helper_script)
        helper_path = Path(tmp.name)

    output_path = output_dir / f"{_safe_name(endpoint)}_pyspy.svg"
    try:
        subprocess.run(
            [
                "py-spy",
                "record",
                "-o",
                str(output_path),
                "--format",
                "flamegraph",
                "--",
                sys.executable,
                str(helper_path),
            ],
            check=True,
        )
    finally:
        helper_path.unlink(missing_ok=True)
    return output_path


def _create_engine(database_url: Optional[str]) -> Engine:
    url = database_url or getattr(settings, "database_url_psycopg3", settings.database_url)
    return create_engine(url)


def _fetch_pg_stats(engine: Engine) -> Dict[str, Dict[str, float]]:
    query = text(
        """
        SELECT query, calls, total_exec_time
        FROM pg_stat_statements
        WHERE query NOT ILIKE 'COPY %'
        """
    )
    stats: Dict[str, Dict[str, float]] = {}
    with engine.connect() as conn:
        for row in conn.execute(query):
            stats[row.query] = {
                "calls": float(row.calls),
                "total_exec_time": float(row.total_exec_time),
            }
    return stats


def analyze_database_queries(
    endpoint: str,
    method: str,
    iterations: int,
    base_url: str,
    database_url: Optional[str],
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compare pg_stat_statements before/after hitting the endpoint."""

    engine = _create_engine(database_url)
    before = _fetch_pg_stats(engine)

    asyncio.run(_exercise_endpoint(endpoint, method, iterations, base_url, payload))

    after = _fetch_pg_stats(engine)

    deltas: List[Dict[str, Any]] = []
    for query, stats_after in after.items():
        stats_before = before.get(query, {"calls": 0.0, "total_exec_time": 0.0})
        calls_delta = stats_after["calls"] - stats_before["calls"]
        time_delta = stats_after["total_exec_time"] - stats_before["total_exec_time"]
        if calls_delta > 0:
            deltas.append(
                {
                    "query": query,
                    "calls": calls_delta,
                    "total_exec_time": time_delta,
                    "avg_exec_time": time_delta / calls_delta if calls_delta else 0.0,
                }
            )

    deltas.sort(key=lambda item: item["total_exec_time"], reverse=True)
    return {
        "queries": deltas[:10],
        "iterations": iterations,
    }


def parse_payload(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    import json

    return json.loads(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile FastAPI endpoints")
    parser.add_argument("--endpoint", required=True, help="Endpoint path, e.g. /api/v1/companies")
    parser.add_argument("--method", default="GET", help="HTTP method (GET, POST, ...)")
    parser.add_argument("--iterations", type=int, default=50, help="Number of requests to send")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds for py-spy capture")
    parser.add_argument(
        "--profile-type",
        choices={"cpu", "memory", "pyspy", "queries", "all"},
        default="cpu",
        help="Profiling mode",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL of the API")
    parser.add_argument("--payload", help="JSON payload for POST/PUT requests")
    parser.add_argument("--database-url", help="Override database URL for query analysis")

    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    payload = parse_payload(args.payload)

    if args.profile_type in {"cpu", "all"}:
        cpu_path = profile_endpoint_cpu(
            args.endpoint,
            args.method,
            args.iterations,
            args.base_url,
            args.output_dir,
            payload,
        )
        print(f"CPU profile written to {cpu_path}")

    if args.profile_type in {"memory", "all"}:
        mem_path = profile_endpoint_memory(
            args.endpoint,
            args.method,
            args.iterations,
            args.base_url,
            args.output_dir,
            payload,
        )
        print(f"Memory profile written to {mem_path}")

    if args.profile_type in {"pyspy", "all"}:
        pyspy_path = profile_with_pyspy(
            args.endpoint,
            args.method,
            args.duration,
            args.base_url,
            args.output_dir,
            payload,
        )
        if pyspy_path:
            print(f"py-spy flamegraph written to {pyspy_path}")

    if args.profile_type in {"queries", "all"}:
        report = analyze_database_queries(
            args.endpoint,
            args.method,
            args.iterations,
            args.base_url,
            args.database_url,
            payload,
        )
        report_path = args.output_dir / f"{_safe_name(args.endpoint)}_queries.json"
        import json

        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Database query analysis written to {report_path}")


if __name__ == "__main__":
    import shutil

    main()
