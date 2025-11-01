# Performance Profiling Tools

Profiling scripts support identifying CPU, memory, and database bottlenecks within the API.

## Available Tools

### `profile_endpoint.py`

- Profiles FastAPI endpoints via HTTP requests.
- Modes: `cpu`, `memory`, `pyspy`, `queries`, or `all`.
- Outputs cProfile stats, memory usage reports, py-spy flamegraphs, and query deltas.

**Usage examples:**

```bash
python scripts/profiling/profile_endpoint.py --endpoint /api/v1/companies --profile-type cpu
python scripts/profiling/profile_endpoint.py --endpoint /api/v1/export/companies/stats --profile-type memory
python scripts/profiling/profile_endpoint.py --endpoint /api/v1/companies --profile-type queries --iterations 100
```

### `analyze_slow_queries.py`

- Analyzes PostgreSQL slow queries using `pg_stat_statements`.
- Generates Markdown report with EXPLAIN plans and index suggestions.

**Usage examples:**

```bash
python scripts/profiling/analyze_slow_queries.py --limit 20
python scripts/profiling/analyze_slow_queries.py --enable-extension --database-url postgresql://user:pass@host/db
```

## Workflow

1. **Identify target endpoint or query** from load test or monitoring data.
2. **Profile endpoint** using `profile_endpoint.py` selecting relevant mode.
3. **Analyze database impact** with `--profile-type queries` or `analyze_slow_queries.py`.
4. **Implement optimizations** (caching, indexes, code changes).
5. **Re-run profiling** to confirm improvements.
6. **Document findings** in `docs/PERFORMANCE.md`.

## Output Locations

- Profiling results saved under `data/profiling/`.
- Slow query reports written to `data/profiling/slow_queries_report.md` by default.
- Flamegraphs stored as SVG files for visualization.

## Prerequisites

- Ensure API is running locally or provide `--base-url`.
- For query analysis: PostgreSQL must have `pg_stat_statements` extension enabled.
- Optional: `py-spy` installed for flamegraph generation.

## Best Practices

1. Profile against realistic data volumes (seed using load tests).
2. Warm caches before profiling to observe steady-state behaviour.
3. Capture before/after metrics to validate improvements.
4. Use profiling during performance regressions identified in CI or monitoring.
