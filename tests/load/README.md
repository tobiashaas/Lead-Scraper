# Load Testing Guide

Comprehensive load testing for the Lead Scraper API ensures consistent
performance under realistic usage patterns.

## Overview

- **Framework**: Locust (Python-based load testing with Web UI)
- **Scenarios**: Mixed workload, bulk operations, export heavy
- **Integration**: Prometheus metrics exporter for Grafana dashboards

## Quick Start

```bash
# Via Makefile (recommended)
make load-test

# With Web UI
docker-compose up -d  # ensure services running
make load-test-ui  # open http://localhost:8089

# Specific scenario
make load-test-bulk
make load-test-export
```

## Scenarios

### Mixed Workload (`tests/load/locustfile.py`)

- Simulates realistic user behaviour
- 80% read, 15% write, 5% admin
- Weighted tasks for pagination, search, CRUD, exports

### Bulk Operations (`tests/load/scenarios/bulk_operations.py`)

- High throughput bulk updates and status changes
- Validates database write performance
- Targets bulk update, delete, restore endpoints

### Export Heavy (`tests/load/scenarios/export_heavy.py`)

- Large CSV/JSON exports (up to 10k records)
- Measures streaming performance and memory impact
- Exercises expensive aggregation endpoints

## Performance Targets

| Endpoint Type | p95 Latency | Error Rate | Throughput |
| ------------- | ----------- | ---------- | ---------- |
| Simple GET    | < 100ms     | < 0.5%     | 500+ rpm   |
| List/Search   | < 200ms     | < 1%       | 300+ rpm   |
| Aggregations  | < 500ms     | < 1%       | 100+ rpm   |
| Exports       | < 2000ms    | < 2%       | 50+ rpm    |
| Bulk Ops      | < 1000ms    | < 1%       | 100+ rpm   |

## Running Tests

1. Ensure API, database, and Redis are running (`make docker-up`).
2. Seed load-testing data if required:

   ```bash
   make load-test-seed
   ```

3. Execute the desired scenario (`make load-test`, `make load-test-bulk`, etc.).
4. Inspect CSV/HTML results in `data/load_tests/`.
5. Analyse results via `make load-test-analyze`.
6. Review Grafana "Load Testing" dashboard for real-time metrics.

## Result Analysis

- **HTML Report**: `data/load_tests/<scenario>_report.html`
- **CSV Stats**: `data/load_tests/<scenario>_stats.csv`
- **Automated Analysis**: `make load-test-analyze`
- **Grafana Dashboard**: `monitoring/grafana/dashboards/load-testing.json`

## Best Practices

1. Seed realistic datasets (≥10k companies) before load tests.
2. Warm up caches with short runs before long tests.
3. Monitor Prometheus/Grafana during tests for pool usage, errors, latency.
4. Increment user count gradually to identify break points.
5. Save baseline results for regression comparison.
6. Avoid running heavy tests on production without a maintenance window.

## Troubleshooting

| Issue | Resolution |
| ----- | ---------- |
| Authentication failures | Verify `LOAD_TEST_USER_EMAIL` and password env vars |
| No company IDs in pool | Run `make load-test-seed` to populate data |
| Locust metrics missing | Ensure `locust-plugins` installed and exporter started |
| High error rate | Check API logs, database pool saturation, missing indexes |
| CSV export slow | Verify GZip middleware enabled and caching working |

## Related Documentation

- [Performance Guide](../../docs/PERFORMANCE.md)
- [Profiling Tools](../../scripts/profiling/README.md)
- [Performance Workflow](../../docs/PRODUCTION.md)
