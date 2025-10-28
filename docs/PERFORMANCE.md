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

### Load Testing

```bash
# Install locust
pip install locust

# Run load test
locust -f tests/load_test.py --host=http://localhost:8000
```

Example load test:

```python
# tests/load_test.py
from locust import HttpUser, task, between

class APIUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Login
        response = self.client.post("/api/v1/auth/login", json={
            "username": "test",
            "password": "test"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def list_companies(self):
        self.client.get(
            "/api/v1/companies?limit=100",
            headers=self.headers
        )

    @task(1)
    def get_company(self):
        self.client.get(
            "/api/v1/companies/1",
            headers=self.headers
        )

    @task(1)
    def export_stats(self):
        self.client.get(
            "/api/v1/export/companies/stats",
            headers=self.headers
        )
```

---

## 🔧 Optimization Checklist

### Database
- [x] Add indexes for common queries
- [ ] Enable connection pooling
- [ ] Configure query timeout
- [ ] Set up read replicas (if needed)
- [ ] Implement query result caching
- [ ] Regular VACUUM and ANALYZE

### API
- [ ] Enable response compression
- [ ] Implement Redis caching
- [ ] Use async/await everywhere
- [ ] Optimize serialization
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
- Multiple API instances behind load balancer
- Database read replicas
- Distributed caching (Redis Cluster)
- Separate scraping workers

### Microservices (Future)
- Separate scraping service
- Separate scoring service
- Separate export service
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
