# 📚 API Documentation

## Overview

The KR Lead Scraper API is a comprehensive REST API for automated B2B lead generation. It provides endpoints for multi-source scraping, AI-powered enrichment, lead scoring, duplicate detection, contact verification, and data export.

### Features

- 🔍 **Multi-Source Scraping**: Extract leads from 11880, Gelbe Seiten, Unternehmensverzeichnis, and more
- 🤖 **AI-Powered Enrichment**: Intelligent data extraction using Ollama (LLaMA, Mistral, Qwen models)
- 📊 **Lead Scoring**: Automated quality assessment based on data completeness and quality indicators
- 🔄 **Duplicate Detection**: Smart deduplication with configurable similarity thresholds
- ✅ **Contact Verification**: Email SMTP verification and enhanced phone validation
- 📤 **Export**: CSV and JSON exports with filtering and pagination
- 🔔 **Webhooks**: Real-time event notifications with HMAC signatures
- 🔐 **JWT Authentication**: Secure role-based access control (User/Admin roles)

### Base URLs

- **Development**: `http://localhost:8000`
- **Staging**: `https://staging.your-domain.com`
- **Production**: `https://api.your-domain.com`

### API Version

**Current Version**: v1 (1.0.0)

All endpoints are prefixed with `/api/v1`. See [API Versioning Strategy](API-VERSIONING.md) for details on versioning policy and future migrations.

### Interactive Documentation

- **Swagger UI**: `http://localhost:8000/docs` - Interactive API explorer with "Try it out" functionality
- **ReDoc**: `http://localhost:8000/redoc` - Alternative documentation with better readability
- **OpenAPI JSON**: `http://localhost:8000/openapi.json` - OpenAPI 3.1 schema for client generation

---

## Quick Start

### 1. Authentication

Register a new user and obtain JWT tokens:

```bash
# Register user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "demo_user",
    "email": "demo@example.com",
    "password": "SecurePassword123!",
    "full_name": "Demo User"
  }'

# Login to get tokens
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "demo_user",
    "password": "SecurePassword123!"
  }'

# Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 2. Use Access Token

Include the access token in the `Authorization` header for all protected endpoints:

```bash
export TOKEN="your_access_token_here"

curl -X GET http://localhost:8000/api/v1/companies \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Create Scraping Job

```bash
curl -X POST http://localhost:8000/api/v1/scraping/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "source_name": "11880",
    "city": "Stuttgart",
    "industry": "IT-Service",
    "max_pages": 3,
    "use_ai": true,
    "enable_smart_scraper": true
  }'
```

---

## Authentication Flow

### JWT Authentication

The API uses JWT (JSON Web Tokens) for authentication with two token types:

- **Access Token**: Short-lived token (30 minutes) for API requests
- **Refresh Token**: Long-lived token (7 days) for obtaining new access tokens

### Token Lifecycle

```
1. Register → 2. Login → 3. Get Access Token → 4. Use Token in Requests
                ↓
           5. Token Expires (30min) → 6. Refresh Token → 7. New Access Token
```

### Authentication Endpoints

#### POST /api/v1/auth/register
Register a new user account.

**Request Body**:
```json
{
  "username": "demo_user",
  "email": "demo@example.com",
  "password": "SecurePassword123!",
  "full_name": "Demo User"
}
```

**Response** (201 Created):
```json
{
  "id": 1,
  "username": "demo_user",
  "email": "demo@example.com",
  "full_name": "Demo User",
  "role": "user",
  "is_active": true,
  "created_at": "2025-01-18T10:00:00Z"
}
```

#### POST /api/v1/auth/login
Login and obtain JWT tokens.

**Request Body**:
```json
{
  "username": "demo_user",
  "password": "SecurePassword123!"
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### POST /api/v1/auth/refresh
Refresh access token using refresh token.

**Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### GET /api/v1/auth/me
Get current user profile (requires authentication).

**Response** (200 OK):
```json
{
  "id": 1,
  "username": "demo_user",
  "email": "demo@example.com",
  "full_name": "Demo User",
  "role": "user",
  "is_active": true,
  "created_at": "2025-01-18T10:00:00Z"
}
```

### Security Features

- **Account Lockout**: Account locks for 1 hour after 5 failed login attempts
- **Password Requirements**: Minimum 8 characters
- **Role-Based Access**: User (default) and Admin roles
- **Token Rotation**: New refresh token issued on each refresh
- **Secure Headers**: Authorization header with Bearer scheme

---

## Endpoint Reference

### Companies API

Manage company/lead records with full CRUD operations.

#### GET /api/v1/companies
List companies with pagination and filtering.

**Query Parameters**:
- `skip` (int, default: 0): Number of records to skip (pagination offset)
- `limit` (int, default: 100, max: 1000): Maximum records to return
- `city` (string): Filter by city name (case-insensitive partial match)
- `industry` (string): Filter by industry sector
- `lead_status` (enum): Filter by status (new, contacted, qualified, converted, lost)
- `lead_quality` (enum): Filter by quality (A, B, C, D, unknown)
- `search` (string): Search across company name, email, and website
- `include_total` (bool, default: true): Include total count (disable for faster pagination)

**Response** (200 OK):
```json
{
  "total": 250,
  "skip": 0,
  "limit": 10,
  "items": [
    {
      "id": 1,
      "company_name": "Tech Solutions GmbH",
      "legal_form": "GmbH",
      "industry": "IT-Service",
      "website": "https://www.tech-solutions.de",
      "email": "info@tech-solutions.de",
      "phone": "+49 711 123456",
      "city": "Stuttgart",
      "postal_code": "70173",
      "lead_status": "new",
      "lead_quality": "A",
      "lead_score": 85,
      "is_active": true,
      "created_at": "2025-01-18T10:00:00Z"
    }
  ]
}
```

#### GET /api/v1/companies/{id}
Get company details by ID.

**Response** (200 OK): Full company object with all fields.

**Error** (404 Not Found):
```json
{
  "detail": "Company not found"
}
```

#### POST /api/v1/companies
Create a new company.

**Request Body**:
```json
{
  "company_name": "Tech Solutions GmbH",
  "legal_form": "GmbH",
  "industry": "IT-Service",
  "website": "https://www.tech-solutions.de",
  "email": "info@tech-solutions.de",
  "phone": "+49 711 123456",
  "city": "Stuttgart",
  "postal_code": "70173"
}
```

**Response** (201 Created): Created company object.

**Error** (409 Conflict):
```json
{
  "detail": "Company with this name already exists in this city"
}
```

#### PUT /api/v1/companies/{id}
Update company (partial update supported).

**Request Body**: Any subset of company fields.

**Response** (200 OK): Updated company object.

#### DELETE /api/v1/companies/{id}
Soft delete company (sets `is_active=False`).

**Response** (200 OK):
```json
{
  "message": "Company deleted successfully"
}
```

#### GET /api/v1/companies/stats/overview
Get company statistics (cached for 5 minutes).

**Response** (200 OK):
```json
{
  "total_companies": 1250,
  "active_companies": 1180,
  "by_status": {
    "new": 450,
    "contacted": 320,
    "qualified": 280,
    "converted": 130
  },
  "by_quality": {
    "A": 280,
    "B": 450,
    "C": 320,
    "D": 130
  },
  "top_cities": [
    {"city": "Stuttgart", "count": 180},
    {"city": "München", "count": 150}
  ]
}
```

---

### Scraping API

Create and manage scraping jobs for lead extraction.

#### POST /api/v1/scraping/jobs
Create and start a scraping job.

**Request Body**:
```json
{
  "source_name": "11880",
  "city": "Stuttgart",
  "industry": "IT-Service",
  "max_pages": 3,
  "use_tor": true,
  "use_ai": true,
  "enable_smart_scraper": true,
  "smart_scraper_mode": "enrichment",
  "smart_scraper_max_sites": 10
}
```

**Response** (201 Created):
```json
{
  "id": 123,
  "source_name": "11880",
  "city": "Stuttgart",
  "industry": "IT-Service",
  "status": "pending",
  "created_at": "2025-01-18T10:00:00Z",
  "rq_job_id": "abc-123-def"
}
```

**Description**: Job runs asynchronously in background worker. Poll `GET /jobs/{id}` to check progress.

#### GET /api/v1/scraping/jobs
List scraping jobs with pagination.

**Query Parameters**:
- `skip`, `limit`: Pagination
- `status`: Filter by status (pending, running, completed, failed, cancelled)

#### GET /api/v1/scraping/jobs/{id}
Get job details including progress and results.

**Response** (200 OK):
```json
{
  "id": 123,
  "source_name": "11880",
  "status": "completed",
  "progress": 100,
  "results_count": 25,
  "new_companies": 15,
  "updated_companies": 10,
  "duration_seconds": 180,
  "completed_at": "2025-01-18T10:03:00Z"
}
```

#### DELETE /api/v1/scraping/jobs/{id}
Cancel a running job.

**Response** (200 OK):
```json
{
  "message": "Job cancelled successfully"
}
```

**Error** (400 Bad Request):
```json
{
  "detail": "Cannot cancel completed job"
}
```

#### GET /api/v1/scraping/jobs/stats
Get queue statistics.

**Response** (200 OK):
```json
{
  "queued": 5,
  "started": 2,
  "finished": 150,
  "failed": 3
}
```

---

### Export API

Export company data in various formats.

#### GET /api/v1/export/companies/csv
Export companies as CSV (streaming response).

**Query Parameters**: Same filters as `GET /companies` (city, industry, status, quality, search)
- `limit`: Maximum 10,000 companies per export

**Response** (200 OK): CSV file download with headers:
```
Content-Type: text/csv
Content-Disposition: attachment; filename=companies_export_20250118.csv
```

#### GET /api/v1/export/companies/json
Export companies as JSON.

**Response** (200 OK):
```json
{
  "export_date": "2025-01-18T10:00:00Z",
  "total_companies": 25,
  "filters": {
    "city": "Stuttgart",
    "industry": "IT-Service"
  },
  "companies": [...]
}
```

#### GET /api/v1/export/companies/stats
Export aggregated statistics (cached for 5 minutes).

---

### Lead Scoring API

Automated lead quality assessment.

#### POST /api/v1/scoring/companies/{id}
Score a single company.

**Response** (200 OK):
```json
{
  "company_id": 1,
  "score": 85,
  "quality": "A",
  "breakdown": {
    "data_completeness": 40,
    "contact_quality": 25,
    "verification_status": 20
  },
  "recommendations": [
    "Add company description for +5 points",
    "Verify email address for +10 points"
  ]
}
```

#### POST /api/v1/scoring/companies/bulk
Bulk score companies.

**Request Body**:
```json
{
  "company_ids": [1, 2, 3],
  "filters": {
    "lead_status": "new",
    "lead_quality": "unknown"
  }
}
```

**Response** (200 OK):
```json
{
  "scored_count": 25,
  "average_score": 72,
  "quality_distribution": {
    "A": 5,
    "B": 10,
    "C": 8,
    "D": 2
  }
}
```

#### GET /api/v1/scoring/stats
Get scoring statistics.

---

### Bulk Operations API

Mass operations on multiple companies.

#### POST /api/v1/bulk/companies/update
Bulk update companies.

**Request Body**:
```json
{
  "company_ids": [1, 2, 3],
  "updates": {
    "lead_status": "contacted",
    "notes": "Contacted via email"
  }
}
```

**Response** (200 OK):
```json
{
  "updated_count": 3,
  "failed_ids": []
}
```

#### POST /api/v1/bulk/companies/delete
Bulk soft delete companies.

#### POST /api/v1/bulk/companies/status
Bulk change lead status or quality.

#### POST /api/v1/bulk/companies/restore
Bulk restore soft-deleted companies.

---

### Webhooks API

Event notification webhooks with HMAC signatures.

#### POST /api/v1/webhooks
Create a webhook.

**Request Body**:
```json
{
  "url": "https://your-app.com/webhooks/kr-leads",
  "events": ["job.completed", "duplicate.detected"],
  "secret": "your_webhook_secret",
  "active": true
}
```

**Response** (201 Created): Webhook object.

#### GET /api/v1/webhooks
List user's webhooks.

#### GET /api/v1/webhooks/{id}
Get webhook details.

#### PATCH /api/v1/webhooks/{id}
Update webhook.

#### DELETE /api/v1/webhooks/{id}
Delete webhook.

#### POST /api/v1/webhooks/{id}/test
Send test event to webhook URL.

**Webhook Events**:
- `job.completed`: Scraping job finished
- `job.failed`: Scraping job failed
- `company.created`: New company created
- `company.updated`: Company updated
- `duplicate.detected`: Duplicate candidate created
- `duplicate.merged`: Duplicates merged
- `contact.verified`: Contact verification completed

**Webhook Payload Format**:
```json
{
  "event": "job.completed",
  "timestamp": "2025-01-18T10:30:00Z",
  "webhook_id": 123,
  "payload": {
    "job_id": 456,
    "results_count": 25
  }
}
```

**HMAC Signature**: Sent in `X-Webhook-Signature` header for verification.

---

### Duplicates API

Duplicate detection and management.

#### GET /api/v1/duplicates/candidates
List duplicate candidates.

#### POST /api/v1/duplicates/candidates/{id}/merge
Merge duplicate companies.

#### POST /api/v1/duplicates/candidates/{id}/reject
Reject false positive.

#### POST /api/v1/duplicates/scan
Trigger duplicate scan (admin only).

#### GET /api/v1/duplicates/stats
Get duplicate statistics.

---

### Health API

Health checks and metrics for monitoring.

#### GET /health
Basic health check (always returns 200 if API is running).

**Response** (200 OK):
```json
{
  "status": "healthy",
  "timestamp": "2025-01-18T10:00:00Z"
}
```

#### GET /health/detailed
Detailed health check for all dependencies.

**Response** (200 OK):
```json
{
  "status": "healthy",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "ollama": "healthy"
  }
}
```

#### GET /health/ready
Kubernetes readiness probe.

#### GET /health/live
Kubernetes liveness probe.

#### GET /metrics
Prometheus metrics in text format.

---

## Common Patterns

### Pagination

All list endpoints support pagination:

```bash
GET /api/v1/companies?skip=0&limit=50
```

**Response Format**:
```json
{
  "total": 1250,
  "skip": 0,
  "limit": 50,
  "items": [...]
}
```

**Performance Tip**: Set `include_total=false` for faster pagination (skips COUNT query).

### Filtering

Case-insensitive partial matching:

```bash
GET /api/v1/companies?city=Stuttgart&industry=IT-Service
```

### Search

Search across multiple fields:

```bash
GET /api/v1/companies?search=GmbH
```

Searches: company name, email, website

### Error Responses

Standard error format:

```json
{
  "detail": "Error message"
}
```

**HTTP Status Codes**:
- `400 Bad Request`: Invalid input, validation errors
- `401 Unauthorized`: Missing or invalid token
- `403 Forbidden`: Insufficient permissions, account locked
- `404 Not Found`: Resource not found
- `409 Conflict`: Duplicate resource
- `422 Unprocessable Entity`: Validation error (Pydantic)
- `500 Internal Server Error`: Server error

---

## Code Examples

### Python (httpx)

```python
import httpx

# Login
response = httpx.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"username": "demo_user", "password": "SecurePassword123!"}
)
token = response.json()["access_token"]

# List companies
response = httpx.get(
    "http://localhost:8000/api/v1/companies",
    headers={"Authorization": f"Bearer {token}"},
    params={"city": "Stuttgart", "limit": 50}
)
companies = response.json()["items"]

# Create scraping job
response = httpx.post(
    "http://localhost:8000/api/v1/scraping/jobs",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "source_name": "11880",
        "city": "Stuttgart",
        "industry": "IT-Service",
        "max_pages": 3
    }
)
job = response.json()
```

### JavaScript (fetch)

```javascript
// Login
const loginResponse = await fetch('http://localhost:8000/api/v1/auth/login', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({username: 'demo_user', password: 'SecurePassword123!'})
});
const {access_token} = await loginResponse.json();

// Create scraping job
const jobResponse = await fetch('http://localhost:8000/api/v1/scraping/jobs', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${access_token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    source_name: '11880',
    city: 'Stuttgart',
    industry: 'IT-Service',
    max_pages: 3
  })
});
const job = await jobResponse.json();
```

### cURL

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo_user","password":"SecurePassword123!"}' \
  | jq -r '.access_token')

# List companies
curl -X GET "http://localhost:8000/api/v1/companies?city=Stuttgart&limit=10" \
  -H "Authorization: Bearer $TOKEN"

# Create company
curl -X POST http://localhost:8000/api/v1/companies \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "New Company GmbH",
    "city": "Stuttgart",
    "industry": "IT-Service"
  }'
```

---

## Rate Limiting

**Default Limits**: 100 requests per minute per user

**Headers**:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Timestamp when limit resets

**Response** (429 Too Many Requests):
```json
{
  "detail": "Rate limit exceeded. Try again in 30 seconds."
}
```

---

## API Versioning

**Current Version**: v1 (1.0.0)

All endpoints use `/api/v1` prefix. See [API-VERSIONING.md](API-VERSIONING.md) for:
- Versioning strategy (URL-based)
- Breaking vs. non-breaking changes
- Deprecation policy (6 months notice)
- Migration guides

---

## Best Practices

1. **Use HTTPS in production** - Never send tokens over HTTP
2. **Store tokens securely** - Use secure storage, not localStorage for web apps
3. **Refresh tokens before expiration** - Implement automatic token refresh
4. **Handle errors gracefully** - Check status codes, parse error details
5. **Use pagination** - Set appropriate `limit` for large datasets
6. **Enable compression** - Send `Accept-Encoding: gzip` header
7. **Monitor rate limits** - Check `X-RateLimit-*` headers
8. **Validate input** - Use provided schemas for client-side validation

---

## SDKs & Client Libraries

### OpenAPI Generator

Generate client libraries from OpenAPI schema:

```bash
# Download schema
curl http://localhost:8000/openapi.json > openapi.json

# Generate Python client
openapi-generator-cli generate \
  -i openapi.json \
  -g python \
  -o ./client

# Generate TypeScript client
openapi-generator-cli generate \
  -i openapi.json \
  -g typescript-fetch \
  -o ./client
```

---

## Support & Resources

### Documentation

- [API Reference](http://localhost:8000/docs) - Interactive Swagger UI
- [ReDoc](http://localhost:8000/redoc) - Alternative API documentation
- [Production Guide](PRODUCTION.md) - Deployment and configuration
- [Performance Guide](PERFORMANCE.md) - Optimization and load testing
- [Testing Guide](TESTING_GUIDE.md) - Running tests

### Support

- **GitHub Issues**: [Report bugs and feature requests](https://github.com/your-org/lead-scraper/issues)
- **Email**: support@kunze-ritter.de
- **Documentation**: `docs/` directory in repository

---

## Changelog

See [CHANGELOG.md](../CHANGELOG.md) for version history and release notes.
