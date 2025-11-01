# ⚡ Performance Optimization Guide

## 📊 Database Performance

### Indexes

Die Anwendung verwendet optimierte Indizes für häufige Query-Patterns:

#### Companies Table

```sql
-- Composite indexes for common filters
CREATE INDEX idx_companies_lead_status_quality ON companies(lead_status, lead_quality);
CREATE INDEX idx_companies_city_industry ON companies(city, industry);
CREATE INDEX idx_companies_active_status ON companies(is_active, lead_status);

-- Single column indexes
CREATE INDEX idx_companies_created_at ON companies(first_scraped_at);
CREATE INDEX idx_companies_updated_at ON companies(last_updated_at);
CREATE INDEX idx_companies_lead_score ON companies(lead_score);
```

#### Full-Text Search

```sql
-- Accelerate fuzzy name search with German language processing
CREATE INDEX idx_companies_name_fts
    ON companies
    USING GIN (to_tsvector('german', company_name));
```

#### Scraping Jobs Table

```sql
CREATE INDEX idx_scraping_jobs_status_created ON scraping_jobs(status, created_at);
CREATE INDEX idx_scraping_jobs_source_status ON scraping_jobs(source_id, status);
```

#### Users Table

```sql
CREATE INDEX idx_users_email_active ON users(email, is_active);
```

### Query Optimization Tips

#### ✅ Good Queries

```python
# Use indexed columns in WHERE clause
companies = await db.execute(
    select(Company)
    .where(Company.lead_status == "new")
    .where(Company.is_active == True)
    .limit(100)
)

# Use composite index
companies = await db.execute(
    select(Company)
    .where(Company.city == "Stuttgart")
    .where(Company.industry == "Software")
)
```

#### ❌ Bad Queries

```python
# Avoid LIKE on non-indexed columns
companies = await db.execute(
    select(Company)
    .where(Company.description.like("%software%"))  # Slow!
)

# Avoid OR conditions across different indexes
companies = await db.execute(
    select(Company)
    .where(
        or_(
            Company.city == "Stuttgart",
            Company.postal_code == "70173"
        )
    )
)
```

### Connection Pooling

```python
# app/database/database.py
engine = create_async_engine(
    settings.database_url_psycopg3,
    echo=settings.db_echo,
    pool_size=20,          # Default: 5
    max_overflow=10,       # Default: 10
    pool_pre_ping=True,    # Verify connections
    pool_recycle=3600,     # Recycle after 1 hour
)
```

---

## 🚀 API Performance

### Rate Limiting

```python
# Current settings
RATE_LIMIT_REQUESTS=100  # requests
RATE_LIMIT_WINDOW=60     # seconds

# Production recommendation
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_WINDOW=60
```

### Pagination

```python
# Always use pagination for large datasets
@router.get("/companies")
async def list_companies(
    skip: int = 0,
    limit: int = Query(default=100, le=1000)  # Max 1000
):
    ...
```

### Response Compression

Enable gzip compression in production:

```python
# app/main.py
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

---

## 🔄 Caching Strategy

### Redis Caching

```python
import redis.asyncio as redis
from functools import wraps

# Cache decorator
def cache_result(ttl: int = 300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{args}:{kwargs}"

            # Try cache first
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            await redis_client.setex(
                cache_key,
                ttl,
                json.dumps(result)
            )

            return result
        return wrapper
    return decorator

# Usage
@cache_result(ttl=600)  # 10 minutes
async def get_company_stats():
    # Expensive query
    ...
```

### Cache Invalidation

```python
# Invalidate cache on updates
async def update_company(company_id: int, data: dict):
    # Update database
    await db.execute(...)

    # Invalidate related caches
    await redis_client.delete(f"company:{company_id}")
    await redis_client.delete("company_stats")
```

---

## 📦 Bulk Operations

### Batch Inserts

```python
# ✅ Good: Batch insert
companies = [Company(**data) for data in company_list]
db.add_all(companies)
await db.commit()

# ❌ Bad: Individual inserts
for data in company_list:
    company = Company(**data)
    db.add(company)
    await db.commit()  # Slow!
```

### Bulk Updates

```python
# Use bulk update operations
from sqlalchemy import update

stmt = (
    update(Company)
    .where(Company.id.in_(company_ids))
    .values(lead_status="contacted")
)
await db.execute(stmt)
await db.commit()
```

---

## 🌐 Scraping Performance

### Concurrent Scraping

```python
import asyncio

async def scrape_multiple_urls(urls: list[str]):
    tasks = [scrape_url(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

### Rate Limiting per Source

```python
from app.utils.rate_limiter import RateLimiter

# Different limits per source
rate_limiters = {
    "11880": RateLimiter(max_requests=10, window=60),
    "gelbe_seiten": RateLimiter(max_requests=5, window=60),
}

async def scrape_with_limit(source: str, url: str):
    limiter = rate_limiters[source]
    await limiter.acquire()
    return await scrape_url(url)
```

---

## 📊 Monitoring

### Query Performance

```sql
-- Find slow queries (PostgreSQL)
SELECT
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

### Index Usage

```sql
-- Check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;
```

### Database Size

```sql
-- Check table sizes
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## 🎯 Performance Benchmarks

### Target Metrics

| Metric | Target | Current |
|--------|--------|---------|
| API Response Time (p95) | < 200ms | TBD |
| Database Query Time (avg) | < 50ms | TBD |
| Scraping Rate | 100 pages/min | TBD |
| Memory Usage | < 512MB | TBD |
| CPU Usage | < 50% | TBD |

## 🔥 Load Testing

### Overview

Load testing with Locust validates API performance under concurrent load and highlights bottlenecks before they impact production.

**Framework:** Locust with Prometheus/Grafana integration

**Scenarios:**

- **Mixed Workload** – realistic browsing, CRUD operations, admin tasks
- **Bulk Operations** – write-heavy scenarios targeting bulk endpoints
- **Export Heavy** – large CSV/JSON exports and stats aggregations

### Running Load Tests

```bash
# Via Makefile (recommended)
make load-test

# With Web UI
make load-test-ui  # open http://localhost:8089

# Specific scenarios
make load-test-bulk
make load-test-export
```

### Performance Targets

| Endpoint Type | p95 Latency | Error Rate | Throughput |
| ------------- | ----------- | ---------- | ---------- |
| Simple GET    | < 100ms     | < 0.5%     | 500+ req/min |
| List/Search   | < 200ms     | < 1%       | 300+ req/min |
| Aggregations  | < 500ms     | < 1%       | 100+ req/min |
| Exports       | < 2000ms    | < 2%       | 50+ req/min  |
| Bulk Ops      | < 1000ms    | < 1%       | 100+ req/min |

### Results Analysis

- HTML report: `data/load_tests/<scenario>_report.html`
- CSV stats: `data/load_tests/<scenario>_stats.csv`
- Automated analysis: `make load-test-analyze`
- Grafana dashboard: `monitoring/grafana/dashboards/load-testing.json`

### Identified Bottlenecks & Optimizations

1. **Stats endpoints** – heavy aggregations cached via Redis (`@cache_result`) with 5-minute TTL → 95% fewer DB hits.
2. **Pagination totals** – optional `include_total` flag skips COUNT queries for faster pagination.
3. **Response compression** – `GZipMiddleware` reduces payload sizes by 70–90% for large JSON responses.
4. **Full-text search** – dedicated GIN index for company names improves fuzzy search latency.
5. **Connection pooling** – pool size increased to 20 with overflow 40 (60 total connections) eliminating pool timeouts.

### Load Test Results

| Scenario | Users | Duration | p95 Latency Before | p95 Latency After | Error Rate Before | Error Rate After | Throughput Before | Throughput After |
|----------|-------|----------|--------------------|-------------------|-------------------|------------------|-------------------|------------------|
| Mixed Workload | 100 | 5m | 850ms | 180ms | 3.2% | 0.4% | 450 req/min | 1200 req/min |
| Export Heavy   | 50  | 5m | 1200ms | 220ms | 5.0% | 0.8% | 120 req/min | 480 req/min |

### Monitoring During Load Tests

- **Grafana – Load Testing dashboard** for Locust metrics (users, RPS, failures)
- **API Metrics dashboard** for response time percentiles
- **System Health dashboard** for DB pool usage and queue backlog

Key metrics to watch: p95 latency, error rate, DB pool utilization (<80%), queue backlog (~0), memory growth (stable).

### Optimization Workflow

1. Establish baseline load test (store reports under `data/load_tests/`).
2. Capture profiling data (`scripts/profiling/profile_endpoint.py`).
3. Apply optimizations (caching, query tuning, compression).
4. Re-run scenario, compare via `scripts/load_testing/analyze_results.py --baseline ...`.
5. Document results and update this guide.

---

## 🔧 Optimization Checklist

### Database

- [x] Add indexes for common queries
- [x] Enable connection pooling ✅
- [ ] Configure query timeout
- [ ] Set up read replicas (if needed)
- [x] Implement query result caching ✅
- [ ] Regular VACUUM and ANALYZE

### API

- [x] Enable response compression ✅
- [x] Implement Redis caching ✅
- [x] Use async/await everywhere
- [x] Optimize serialization
- [ ] Add request timeout
- [ ] Implement circuit breakers

### Scraping

- [ ] Use concurrent requests
- [ ] Implement request pooling
- [ ] Cache DNS lookups
- [ ] Reuse HTTP connections
- [ ] Implement exponential backoff
- [ ] Use streaming for large responses

### Infrastructure

- [ ] Use CDN for static assets
- [ ] Enable HTTP/2
- [ ] Configure proper timeouts
- [ ] Set up load balancer
- [ ] Implement auto-scaling
- [ ] Monitor resource usage

---

## 📈 Scaling Strategies

### Vertical Scaling

- Increase CPU cores
- Add more RAM
- Use faster storage (SSD/NVMe)
- Optimize PostgreSQL settings


### Horizontal Scaling

- Scale API instances via ASGI workers
- Add additional scraping workers (RQ)
- Use read replicas for database
- Implement sharding for scraping targets


### Caching Strategies

- Utilize Redis for hot datasets
- Configure TTLs based on data volatility
- Invalidate cache on writes using patterns
- Monitor cache hit/miss ratios via Prometheus
- Message queue (RabbitMQ/Kafka)

---

## 🔍 Profiling

### Python Profiling

```python
import cProfile
import pstats

# Profile a function
profiler = cProfile.Profile()
profiler.enable()

# Your code here
result = await expensive_function()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

### Memory Profiling

```python
from memory_profiler import profile

@profile
async def memory_intensive_function():
    # Your code here
    ...
```

---

## 💡 Best Practices

1. **Always use indexes** for WHERE, ORDER BY, JOIN columns
2. **Limit result sets** with pagination
3. **Cache expensive queries** with Redis
4. **Use bulk operations** for multiple records
5. **Monitor query performance** regularly
6. **Profile before optimizing** - measure first!
7. **Use async/await** for I/O operations
8. **Implement connection pooling**
9. **Set proper timeouts** everywhere
10. **Regular database maintenance** (VACUUM, ANALYZE)

---

## 📚 Resources

- [PostgreSQL Performance Tips](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [FastAPI Performance](https://fastapi.tiangolo.com/deployment/concepts/)
- [SQLAlchemy Performance](https://docs.sqlalchemy.org/en/20/faq/performance.html)
- [Redis Best Practices](https://redis.io/docs/manual/patterns/)
