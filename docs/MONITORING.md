# 📊 Monitoring & Observability

## Overview

The monitoring stack combines **Prometheus** for metrics collection and **Grafana** for visualization. It captures API performance, scraping job statistics, queue health, and system status for the KR Lead Scraper platform.

- **Prometheus** collects metrics from the `/metrics` endpoint and stores them in a time-series database.
- **Grafana** provides dashboards for fast insight into API performance, scraping operations, and system health.
- **Custom metrics** from workers and middleware track scraping success rates, duplicates, smart scraper usage, and queue throughput.
- **Alerting** routes critical incidents to email and Slack and is documented in detail in [ALERTING.md](./ALERTING.md).

Dashboards are provisioned automatically for consistent observability across environments.

## Quick Start

```bash
# Start services, including Prometheus and Grafana
make monitoring-up

# Access Grafana
open http://localhost:3000    # Windows: start http://localhost:3000
# Login: admin / admin (change this password!)

# Access Prometheus
open http://localhost:9090

# View raw metrics exposed by the API
curl http://localhost:8000/metrics
```

To stop the monitoring stack:

```bash
make monitoring-down
```

## Architecture

```
API / Worker → Prometheus Client → /metrics endpoint → Prometheus Server → Grafana Dashboards
```

- **MetricsMiddleware** records HTTP request counts, durations, errors, and in-flight requests.
- **app/utils/metrics.py** defines counters and gauges for scraping jobs, duplicate detection, queue sizes, and smart scraper enrichments.
- **/metrics endpoint** in `app/api/health.py` exposes Prometheus-formatted metrics, automatically aggregating multi-process data when enabled.
- **Prometheus** scrapes the API service every 15 seconds (30 seconds in production) and stores metrics on a persistent volume.
- **Grafana** auto-loads dashboards describing API, scraping, and system KPIs.

## Metrics Collected

### HTTP Metrics (MetricsMiddleware)
- `http_requests_total{method,endpoint,status}` – Total requests by method, normalized endpoint, and status.
- `http_request_duration_seconds{method,endpoint}` – Histogram buckets for request latency.
- `http_requests_in_progress{method,endpoint}` – Gauge of in-flight requests.
- `http_errors_total{method,endpoint,error_type}` – Count of exceptions during request processing.

### Scraping Metrics (Worker)
- `scraping_jobs_total{source,status}` – Total jobs by source and final status.
- `scraping_job_duration_seconds{source}` – Histogram buckets for job durations.
- `scraping_results_total{source,result_type}` – Counts of new, updated, and errored results.
- `scraping_jobs_active{source}` – Gauge of concurrent jobs.
- `duplicates_detected_total{action}` – Duplicate handling outcomes (auto merge vs. candidate).
- `smart_scraper_enrichments_total{mode,method}` – Smart scraper usage details.
- `smart_scraper_duration_seconds{method}` – Timing of enrichment per method.
- `contact_verifications_total{contact_type,status}` – Verification counts when enabled.

### Queue Metrics
- `queue_size{queue_name}` – Gauge of queued jobs per queue.
- `queue_jobs_total{queue_name,status}` – Counters for started, finished, failed jobs.

Queue counters use deltas to avoid double-counting when Prometheus restarts.

## Dashboards

Dashboards are provisioned in Grafana under **KR Lead Scraper Dashboards**:

1. **API Metrics**
   - Request and error rates
   - Success rate and percentile latencies
   - Top endpoints and slowest endpoints
   - Active requests gauge

2. **Scraping Statistics**
   - Total jobs, success rate, active jobs
   - Job duration percentiles
   - Result types (new, updated, errors)
   - Duplicate detection and smart scraper usage
   - Queue size and throughput

3. **System Health**
   - Service health indicators (API, DB, Redis, Ollama)
   - Request rate by status, error rate, average latency
   - Active workers and queue backlog

Dashboards can be edited in Grafana and exported back to JSON for version control.

## Configuration

### Environment Variables

`.env.example` and `.env.production.example` define configuration flags:

```bash
PROMETHEUS_ENABLED=True
PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc
METRICS_INCLUDE_LABELS=True
METRICS_ENDPOINT_ENABLED=True
GRAFANA_PASSWORD=admin  # Change for production
```

- `PROMETHEUS_ENABLED` toggles metrics instrumentation globally.
- `PROMETHEUS_MULTIPROC_DIR` enables Uvicorn multi-worker aggregation.
- `METRICS_INCLUDE_LABELS` controls label cardinality (set `False` for minimal labels).
- `METRICS_ENDPOINT_ENABLED` toggles the `/metrics` endpoint.

### Docker Compose

`docker-compose.yml` includes Prometheus and Grafana services with persistent volumes:

- Prometheus: exposed on port 9090 with 30-day retention (development).
- Grafana: exposed on port 3000 with auto-provisioned datasources/dashboards.
- API service mounts `/tmp/prometheus_multiproc` as tmpfs for multiprocess metrics.

Production variants in `docker-compose.prod.yml` limit ports to localhost and extend retention to 90 days.

## Multiprocess Mode

Uvicorn spawns multiple workers in production. To capture metrics correctly:

1. Set `PROMETHEUS_MULTIPROC_DIR` environment variable.
2. Ensure the directory exists (tmpfs mount in Docker Compose).
3. The `/metrics` endpoint aggregates with `multiprocess.MultiProcessCollector` when the environment variable is present.

## Custom Metrics

Add new counters or histograms in `app/utils/metrics.py` and increment them from application code.

Example:

```python
from prometheus_client import Counter
my_feature_total = Counter('my_feature_total', 'Feature events', ['type'])

# In business logic
def process_feature(event_type: str) -> None:
    my_feature_total.labels(type=event_type).inc()
```

Keep label cardinality low; avoid user IDs or dynamic strings.

## Prometheus Queries

Common queries in Prometheus or Grafana Explore:

- Request rate: `sum(rate(http_requests_total[5m])) by (endpoint)`
- Error rate: `sum(rate(http_requests_total{status=~"5.."}[5m]))`
- Latency percentiles: `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))`
- Scraping success rate: `sum(scraping_jobs_total{status="completed"}) / sum(scraping_jobs_total) * 100`
- Queue backlog: `sum(queue_size) by (queue_name)`

## Monitoring in Production

- Prometheus and Grafana ports are bound to localhost; expose them via reverse proxy if needed.
- Configure Grafana admin password (`GRAFANA_PASSWORD`) via secrets manager.
- Use HTTPS and authentication for external Grafana access.
- Adjust Prometheus retention (`--storage.tsdb.retention.time`) based on disk space policies.

## Troubleshooting

| Issue | Resolution |
|-------|------------|
| Metrics missing | Verify `/metrics` reachable, Prometheus target status healthy, check container logs. |
| Grafana shows "No data" | Confirm datasource connectivity, adjust dashboard time range, query Prometheus directly. |
| Metrics double-counted | Confirm multiprocess directory is unique per deployment and cleared on restart. |
| High cardinality | Set `METRICS_INCLUDE_LABELS=False` and ensure endpoint normalization works. |
| Grafana dashboards missing | Check provisioning logs (`docker logs kr-grafana`), ensure JSON file syntax is valid. |

## Best Practices

1. **Review dashboards regularly** to detect regressions.
2. **Set alerts** (Prometheus Alertmanager or Grafana) for latency spikes and failed jobs.
3. **Correlate with Sentry** and structured logs for incidents.
4. **Limit label cardinality** for performance and stability.
5. **Back up Prometheus data volumes** if long-term history is required.

## Related Documentation

- [`docker-compose.yml`](../docker-compose.yml) – local monitoring stack configuration.
- [`docker-compose.prod.yml`](../docker-compose.prod.yml) – production monitoring setup.
- [`app/utils/metrics.py`](../app/utils/metrics.py) – custom metric definitions.
- [`app/middleware/metrics_middleware.py`](../app/middleware/metrics_middleware.py) – HTTP metrics instrumentation.

Happy monitoring! 🚀
