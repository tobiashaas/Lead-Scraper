"""Analyze PostgreSQL slow queries using pg_stat_statements."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings

DEFAULT_DATABASE_URL = settings.database_url_psycopg3 if hasattr(settings, "database_url_psycopg3") else settings.database_url
DEFAULT_OUTPUT = Path("data/profiling/slow_queries_report.md")


@dataclass(slots=True)
class QueryStats:
    query: str
    calls: float
    total_exec_time: float
    mean_exec_time: float
    max_exec_time: float
    stddev_exec_time: float

    @property
    def total_exec_time_ms(self) -> float:
        return self.total_exec_time

    @property
    def mean_exec_time_ms(self) -> float:
        return self.mean_exec_time

    @property
    def max_exec_time_ms(self) -> float:
        return self.max_exec_time


def get_engine(database_url: str) -> Engine:
    return create_engine(database_url)


def enable_pg_stat_statements(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_stat_statements"))
        connection.commit()


def fetch_slow_queries(engine: Engine, limit: int) -> List[QueryStats]:
    query = text(
        """
        SELECT
            query,
            calls,
            total_exec_time,
            mean_exec_time,
            max_exec_time,
            stddev_exec_time
        FROM pg_stat_statements
        WHERE query NOT ILIKE 'VACUUM%'
          AND query NOT ILIKE 'BEGIN%'
          AND query NOT ILIKE 'COMMIT%'
        ORDER BY mean_exec_time DESC
        LIMIT :limit
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(query, {"limit": limit}).fetchall()
    return [
        QueryStats(
            query=row.query,
            calls=float(row.calls),
            total_exec_time=float(row.total_exec_time),
            mean_exec_time=float(row.mean_exec_time),
            max_exec_time=float(row.max_exec_time),
            stddev_exec_time=float(row.stddev_exec_time),
        )
        for row in rows
    ]


def explain_query(engine: Engine, query_text: str) -> List[str]:
    explain = text(f"EXPLAIN (ANALYZE, BUFFERS, VERBOSE) {query_text}")
    try:
        with engine.connect() as connection:
            result = connection.execute(explain)
            return [row[0] for row in result]
    except Exception as exc:  # pragma: no cover - best effort for complex queries
        return [f"Failed to obtain EXPLAIN plan: {exc}"]


def suggest_indexes(explain_plan: Iterable[str]) -> List[str]:
    suggestions: List[str] = []
    plan_text = "\n".join(explain_plan)
    if "Seq Scan" in plan_text and "Index Scan" not in plan_text:
        suggestions.append("Consider adding an index to avoid sequential scans.")
    if "Sort" in plan_text and "rows" in plan_text:
        suggestions.append("Evaluate ORDER BY columns for indexing or reduce result size.")
    if "Hash Join" in plan_text and "Hash Cond" in plan_text:
        suggestions.append("Ensure join columns are indexed to speed up hash joins.")
    return suggestions


def generate_report(queries: List[QueryStats], plans: List[List[str]], suggestions: List[List[str]]) -> str:
    lines: List[str] = []
    lines.append("# Slow Query Analysis Report\n")
    lines.append(f"Total queries analyzed: {len(queries)}\n")

    for idx, stats in enumerate(queries):
        lines.append(f"## Query #{idx + 1}\n")
        lines.append("```sql\n" + stats.query.strip() + "\n```\n")
        lines.append("| Metric | Value |\n")
        lines.append("| --- | ---: |\n")
        lines.append(f"| Calls | {stats.calls:.0f} |\n")
        lines.append(f"| Total execution time (ms) | {stats.total_exec_time_ms:.2f} |\n")
        lines.append(f"| Mean execution time (ms) | {stats.mean_exec_time_ms:.2f} |\n")
        lines.append(f"| Max execution time (ms) | {stats.max_exec_time_ms:.2f} |\n")
        lines.append(f"| Std deviation (ms) | {stats.stddev_exec_time:.2f} |\n")

        plan = plans[idx]
        if plan:
            lines.append("\n<details><summary>EXPLAIN ANALYZE</summary>\n\n")
            lines.append("```text\n" + "\n".join(plan) + "\n```\n")
            lines.append("</details>\n")

        idx_suggestions = suggestions[idx]
        if idx_suggestions:
            lines.append("\n**Suggestions:**\n")
            for suggestion in idx_suggestions:
                lines.append(f"- {suggestion}\n")
        else:
            lines.append("\n_No specific suggestions generated._\n")
        lines.append("\n")

    return "".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze PostgreSQL slow queries")
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL, help="PostgreSQL connection URL")
    parser.add_argument("--limit", type=int, default=20, help="Number of queries to analyze")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Report output path")
    parser.add_argument("--enable-extension", action="store_true", help="Enable pg_stat_statements before analysis")

    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    engine = get_engine(args.database_url)

    if args.enable_extension:
        enable_pg_stat_statements(engine)

    queries = fetch_slow_queries(engine, args.limit)
    plans: List[List[str]] = []
    suggestions: List[List[str]] = []

    for stats in queries:
        plan = explain_query(engine, stats.query)
        plans.append(plan)
        suggestions.append(suggest_indexes(plan))

    report = generate_report(queries, plans, suggestions)
    args.output.write_text(report, encoding="utf-8")
    print(f"Slow query analysis written to {args.output}")

    summary = {
        "queries_analyzed": len(queries),
        "output": str(args.output),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
