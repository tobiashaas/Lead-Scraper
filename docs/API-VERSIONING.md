# API Versioning Strategy

## Overview

This document describes the versioning strategy for the KR Lead Scraper API. Our goal is to provide a stable, predictable API while allowing for future improvements and breaking changes when necessary.

## Versioning Approach

### URL-Based Versioning

We use **URL-based versioning** where the API version is part of the URL path:

- **Current**: `/api/v1/...`
- **Future**: `/api/v2/...` (when breaking changes are needed)

**Rationale**:
- Clear and explicit version in every request
- Easy to route and maintain side-by-side versions
- Simple for clients to understand and implement
- Supports gradual migration between versions

### Version Format

We follow **Semantic Versioning** (SemVer) for the API version number:

```
MAJOR.MINOR.PATCH
```

- **MAJOR**: Breaking changes (requires new version, e.g., v1 → v2)
- **MINOR**: New features (backward compatible, can be added to existing version)
- **PATCH**: Bug fixes (backward compatible, can be added to existing version)

**Current Version**: `1.0.0`

## Breaking vs. Non-Breaking Changes

### Breaking Changes

Breaking changes **require a new major version** (e.g., v1 → v2):

- ❌ Removing endpoints
- ❌ Removing request or response fields
- ❌ Changing field types (e.g., string → integer)
- ❌ Changing authentication mechanism
- ❌ Changing error response format
- ❌ Renaming fields
- ❌ Making optional fields required
- ❌ Changing URL structure

### Non-Breaking Changes

Non-breaking changes **can be added to existing version**:

- ✅ Adding new endpoints
- ✅ Adding optional request fields
- ✅ Adding response fields (clients should ignore unknown fields)
- ✅ Adding new query parameters (optional)
- ✅ Improving error messages
- ✅ Adding new enum values (if clients handle unknown values gracefully)
- ✅ Performance improvements
- ✅ Bug fixes

## Deprecation Policy

### Timeline

When we need to introduce breaking changes:

1. **Deprecation Notice**: 6 months before removal
2. **Maintenance Period**: 6 months (bug fixes only, no new features)
3. **Removal**: In next major version

### Deprecation Process

1. **Mark as Deprecated**:
   - Set `deprecated: true` in OpenAPI schema
   - Add deprecation notice in endpoint description
   - Include deprecation date

2. **Add Response Headers**:
   ```
   X-API-Deprecated: true
   X-API-Deprecation-Date: 2025-07-01
   X-API-Sunset-Date: 2026-01-01
   X-API-Replacement: /api/v2/companies
   ```

3. **Update Documentation**:
   - Add deprecation notice to API.md
   - Provide migration guide
   - Include code examples (before/after)

4. **Notify Users**:
   - Email notification to all API users
   - Changelog entry
   - GitHub release notes
   - In-app notifications (if applicable)

5. **Maintain for 6 Months**:
   - Continue supporting deprecated endpoints
   - Fix critical bugs only
   - No new features

6. **Remove After 6 Months**:
   - Remove in next major version (v2)
   - Return 410 Gone for removed endpoints

### Example Deprecation Notice

```markdown
## ⚠️ Deprecation Notice

**Endpoint**: `GET /api/v1/companies/search`
**Deprecated**: 2025-07-01
**Sunset Date**: 2026-01-01
**Replacement**: `GET /api/v2/companies?search={query}`

This endpoint will be removed in v2. Please migrate to the new search parameter on the companies list endpoint.

### Migration Guide

**Before (v1)**:
```bash
GET /api/v1/companies/search?q=GmbH
```

**After (v2)**:
```bash
GET /api/v2/companies?search=GmbH
```
```

## Version Migration

### v1 to v2 Migration (Future)

When v2 is released, we will provide:

1. **Migration Guide**: Detailed documentation of all breaking changes
2. **Code Examples**: Before/after examples for all changed endpoints
3. **Migration Tool**: Script to help update client code (if applicable)
4. **Side-by-Side Support**: Both v1 and v2 available for 6 months
5. **Testing Environment**: Staging environment with v2 for testing

### Migration Checklist

- [ ] Review breaking changes list
- [ ] Update client code to use v2 endpoints
- [ ] Test in staging environment
- [ ] Update authentication flow (if changed)
- [ ] Update error handling (if changed)
- [ ] Monitor for deprecation warnings
- [ ] Complete migration before v1 sunset date

## Implementation

### Current Implementation (v1)

All routers are registered under `/api/v1` prefix:

```python
# app/main.py
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(companies.router, prefix="/api/v1/companies", tags=["Companies"])
app.include_router(scraping.router, prefix="/api/v1/scraping", tags=["Scraping"])
# ... other routers
```

**Version Configuration**:
```python
# app/core/config.py
api_version: str = Field(default="1.0.0")
api_version_prefix: str = Field(default="/api/v1")
```

### Future v2 Implementation

When v2 is needed:

1. **Create v2 Directory**:
   ```
   app/api/v2/
   ├── __init__.py
   ├── auth.py
   ├── companies.py
   └── ...
   ```

2. **Implement Breaking Changes**:
   - Copy routers from v1
   - Apply breaking changes
   - Update schemas

3. **Register Both Versions**:
   ```python
   # app/main.py
   # v1 (deprecated)
   app.include_router(v1.auth.router, prefix="/api/v1/auth", tags=["Authentication (v1)"])
   
   # v2 (current)
   app.include_router(v2.auth.router, prefix="/api/v2/auth", tags=["Authentication"])
   ```

4. **Maintain for 6 Months**:
   - Both v1 and v2 active
   - v1 receives bug fixes only
   - v2 receives new features

5. **Remove v1**:
   - After 6 months, remove v1 routers
   - Return 410 Gone for v1 endpoints

### Handling Removed Endpoints

```python
# app/api/v1/companies.py (after removal)
@router.get("/search")
async def search_companies_deprecated():
    """Deprecated endpoint - removed in v2"""
    return JSONResponse(
        status_code=410,
        content={
            "error": "Gone",
            "message": "This endpoint has been removed. Please use GET /api/v2/companies?search={query}",
            "deprecated_since": "2025-07-01",
            "removed_on": "2026-01-01",
            "replacement": "/api/v2/companies?search={query}",
            "migration_guide": "https://docs.your-domain.com/api/v2-migration"
        }
    )
```

## Monitoring & Metrics

### Track API Version Usage

Use Prometheus metrics to monitor version usage:

```python
api_version_requests = Counter(
    'api_version_requests_total',
    'Total API requests by version',
    ['version', 'endpoint']
)
```

### Deprecation Warnings

Log deprecation warnings:

```python
logger.warning(
    "Deprecated endpoint accessed",
    extra={
        "endpoint": "/api/v1/companies/search",
        "user_id": user.id,
        "deprecated_since": "2025-07-01",
        "sunset_date": "2026-01-01"
    }
)
```

### Alert on High v1 Usage

Set up alerts when v1 usage is still high near sunset date:

```yaml
# monitoring/prometheus/alerts/api_versioning.yml
- alert: HighDeprecatedAPIUsage
  expr: rate(api_version_requests_total{version="v1"}[5m]) > 10
  for: 1h
  annotations:
    summary: "High usage of deprecated v1 API"
    description: "v1 API is deprecated and will be removed soon"
```

## Best Practices

### For API Developers

1. **Avoid Breaking Changes**: Design APIs to be extensible
2. **Add, Don't Remove**: Add new fields instead of changing existing ones
3. **Use Optional Fields**: Make new fields optional when possible
4. **Version Early**: Plan for versioning from the start
5. **Document Everything**: Clear documentation of all changes
6. **Communicate Early**: Announce deprecations well in advance
7. **Provide Migration Tools**: Help users migrate to new versions

### For API Consumers

1. **Ignore Unknown Fields**: Don't fail on unexpected response fields
2. **Use Specific Versions**: Always specify version in URL
3. **Monitor Deprecation Headers**: Check for `X-API-Deprecated` header
4. **Test Early**: Test new versions in staging before production
5. **Migrate Proactively**: Don't wait until sunset date
6. **Subscribe to Notifications**: Stay informed about API changes
7. **Handle Version Errors**: Gracefully handle 410 Gone responses

## Version History

### v1.0.0 (Current)

**Released**: 2025-01-18

**Features**:
- Multi-source scraping (11880, Gelbe Seiten, etc.)
- AI-powered enrichment with Ollama
- Lead scoring and quality assessment
- Duplicate detection and management
- Contact verification (email SMTP, phone)
- CSV and JSON export
- Webhooks with HMAC signatures
- JWT authentication with role-based access

**Status**: Stable, no breaking changes planned

### v2.0.0 (Future)

**Planned**: TBD

**Potential Breaking Changes**:
- TBD (no breaking changes planned yet)

**Migration Guide**: Will be provided when v2 is announced

## FAQ

### Q: When will v2 be released?

**A**: We have no plans for v2 at this time. v1 is stable and will be maintained for the foreseeable future. We will announce v2 at least 6 months before release.

### Q: Can I use both v1 and v2 simultaneously?

**A**: Yes, during the 6-month transition period, both versions will be available. You can migrate endpoints gradually.

### Q: What happens if I keep using v1 after sunset?

**A**: After the sunset date, v1 endpoints will return `410 Gone` with information about the replacement endpoint.

### Q: How do I know if an endpoint is deprecated?

**A**: Check the `X-API-Deprecated` response header, OpenAPI schema (`deprecated: true`), and API documentation.

### Q: Will minor version updates require code changes?

**A**: No, minor and patch updates are backward compatible. You only need to update for major version changes (v1 → v2).

### Q: How can I test v2 before migrating?

**A**: We will provide a staging environment with v2 available for testing before production release.

## Resources

- [API Documentation](API.md)
- [OpenAPI Schema](http://localhost:8000/openapi.json)
- [Changelog](../CHANGELOG.md)
- [GitHub Releases](https://github.com/your-org/lead-scraper/releases)

## Contact

For questions about API versioning:

- **Email**: support@kunze-ritter.de
- **GitHub Issues**: [Report issues](https://github.com/your-org/lead-scraper/issues)
