# Duplicate Detection

Automatic duplicate detection and merging system for company records.

## Overview

The deduplicator identifies and manages duplicate company entries using fuzzy matching on multiple fields. It operates in two modes:

- **Real-time detection**: During scraping, new companies are checked against existing records
- **Scheduled scans**: Periodic full-database scans to catch duplicates missed during real-time processing

## Similarity Scoring

The system calculates similarity scores for multiple fields:

### Field Weights

- **Name**: 40% (most important)
- **Address**: 20%
- **Phone**: 20%
- **Website**: 20%

### Scoring Algorithm

Each field uses fuzzy string matching (Levenshtein distance) to produce a score from 0-100:

- **Name**: Token sort ratio (handles word order variations)
- **Address**: Token sort ratio (handles formatting differences)
- **Phone**: Exact digit comparison (strips formatting)
- **Website**: Direct string comparison

The **overall similarity** is a weighted average of all field scores.

## Thresholds

Two key thresholds control duplicate handling:

### Auto-Merge Threshold (default: 0.95)

Companies with similarity ≥ 95% are automatically merged during scraping:

- The existing company (primary) is kept
- The new company (duplicate) is merged into primary
- Duplicate is marked inactive with `is_duplicate=True`
- Empty fields in primary are filled from duplicate
- Webhook event `duplicate.merged` is dispatched

### Candidate Threshold (default: 0.80)

Companies with similarity ≥ 80% but < 95% create a `DuplicateCandidate` for manual review:

- Candidate includes both company IDs and all similarity scores
- Status is `pending` until reviewed
- Webhook event `duplicate.detected` is dispatched

## Configuration

All settings are configurable via environment variables:

```bash
# Enable/disable features
DEDUPLICATOR_ENABLED=True
DEDUPLICATOR_REALTIME_ENABLED=True

# Thresholds (0.0-1.0)
DEDUPLICATOR_AUTO_MERGE_THRESHOLD=0.95
DEDUPLICATOR_CANDIDATE_THRESHOLD=0.80

# Field thresholds (0-100)
DEDUPLICATOR_NAME_THRESHOLD=85
DEDUPLICATOR_ADDRESS_THRESHOLD=80
DEDUPLICATOR_PHONE_THRESHOLD=90
DEDUPLICATOR_WEBSITE_THRESHOLD=95

# Scheduled scan
DEDUPLICATOR_SCAN_SCHEDULE="0 2 * * *"  # Cron format
DEDUPLICATOR_SCAN_BATCH_SIZE=100

# Cleanup policy
DEDUPLICATOR_CANDIDATE_RETENTION_DAYS=90
DEDUPLICATOR_CLEANUP_DELETE_CONFIRMED=False
```

### Recommended Settings

**Production** (strict):
- Auto-merge: 0.98 (98%)
- Candidate: 0.85 (85%)
- Higher field thresholds

**Staging** (relaxed):
- Auto-merge: 0.92 (92%)
- Candidate: 0.75 (75%)
- Lower field thresholds to catch more candidates

**Development** (default):
- Auto-merge: 0.95 (95%)
- Candidate: 0.80 (80%)
- Balanced thresholds

## API Endpoints

All endpoints require authentication. Admin endpoints require admin role.

### List Candidates

```http
GET /api/v1/duplicates/candidates?skip=0&limit=50&status=pending&min_similarity=0.8
```

**Query Parameters:**
- `skip`: Pagination offset (default: 0)
- `limit`: Results per page (default: 50, max: 100)
- `status`: Filter by status (`pending`, `confirmed`, `rejected`)
- `min_similarity`: Minimum similarity threshold (0.0-1.0)

**Response:**
```json
{
  "total": 42,
  "skip": 0,
  "limit": 50,
  "items": [
    {
      "id": 123,
      "company_a": {
        "id": 456,
        "company_name": "Tech Solutions GmbH",
        "city": "Berlin",
        "phone": "+49 30 12345678",
        "website": "https://techsolutions.de"
      },
      "company_b": {
        "id": 789,
        "company_name": "TechSolutions GmbH",
        "city": "Berlin",
        "phone": "+49-30-12345678",
        "website": "https://www.techsolutions.de"
      },
      "name_similarity": 0.95,
      "address_similarity": 1.0,
      "phone_similarity": 1.0,
      "website_similarity": 0.98,
      "overall_similarity": 0.97,
      "status": "pending",
      "reviewed_by": null,
      "reviewed_at": null,
      "notes": null,
      "created_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

### Get Candidate Details

```http
GET /api/v1/duplicates/candidates/{candidate_id}
```

Returns full details of a specific duplicate candidate.

### Merge Duplicates

```http
POST /api/v1/duplicates/candidates/{candidate_id}/merge
Content-Type: application/json

{
  "primary_id": 456,
  "duplicate_id": 789,
  "reason": "Same company, different formatting"
}
```

**Permissions:** Authenticated users

Merges the duplicate into the primary company and marks the candidate as `confirmed`.

### Reject Candidate

```http
POST /api/v1/duplicates/candidates/{candidate_id}/reject
Content-Type: application/json

{
  "reason": "Different companies with similar names"
}
```

**Permissions:** Authenticated users

Marks the candidate as `rejected` without merging.

### Trigger Manual Scan

```http
POST /api/v1/duplicates/scan
```

**Permissions:** Admin only

Enqueues a manual duplicate scan job. Returns job ID for tracking.

### Get Statistics

```http
GET /api/v1/duplicates/stats
```

**Permissions:** Authenticated users

Returns aggregate statistics:

```json
{
  "total_candidates": 150,
  "pending": 42,
  "confirmed": 85,
  "rejected": 23,
  "auto_merged": 127
}
```

## Scheduled Jobs

### Duplicate Scan Job

**Schedule:** Configurable via `DEDUPLICATOR_SCAN_SCHEDULE` (default: 2 AM daily)

Scans all active companies in batches:
1. Fetches companies in batches (configurable size)
2. For each company, finds potential duplicates
3. Creates `DuplicateCandidate` records for manual review
4. Dispatches `duplicate.scan_completed` webhook

**Performance:** Uses batched processing to avoid O(N²) complexity.

### Cleanup Job

**Schedule:** Weekly on Sunday at 3 AM

Deletes old duplicate candidates based on retention policy:
- Always deletes `rejected` candidates older than retention period
- Optionally deletes `confirmed` candidates (controlled by `DEDUPLICATOR_CLEANUP_DELETE_CONFIRMED`)
- Default retention: 90 days

## Webhooks

The system dispatches webhook events for duplicate-related actions:

### `duplicate.detected`

Fired when a duplicate candidate is created during scraping.

```json
{
  "event": "duplicate.detected",
  "payload": {
    "company_a_id": 456,
    "company_b_id": 789,
    "similarity": 0.87,
    "job_id": 123,
    "source": "11880"
  }
}
```

### `duplicate.merged`

Fired when duplicates are merged (auto or manual).

```json
{
  "event": "duplicate.merged",
  "payload": {
    "primary_id": 456,
    "duplicate_id": 789,
    "similarity": 0.97,
    "job_id": 123,
    "source": "11880",
    "mode": "auto",
    "reviewed_by": "admin"
  }
}
```

### `duplicate.scan_completed`

Fired when a scheduled scan completes.

```json
{
  "event": "duplicate.scan_completed",
  "payload": {
    "candidates_created": 42,
    "scanned_companies": 15000,
    "timestamp": "2025-01-15T02:00:00Z"
  }
}
```

## Database Schema

### `duplicate_candidates` Table

```sql
CREATE TABLE duplicate_candidates (
    id SERIAL PRIMARY KEY,
    company_a_id INTEGER NOT NULL REFERENCES companies(id),
    company_b_id INTEGER NOT NULL REFERENCES companies(id),
    name_similarity FLOAT,
    address_similarity FLOAT,
    phone_similarity FLOAT,
    website_similarity FLOAT,
    overall_similarity FLOAT,
    status VARCHAR(50) DEFAULT 'pending',
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_duplicate_candidates_status ON duplicate_candidates(status);
CREATE INDEX idx_duplicate_candidates_similarity ON duplicate_candidates(overall_similarity);
```

### `companies` Table Extensions

```sql
ALTER TABLE companies ADD COLUMN is_duplicate BOOLEAN DEFAULT FALSE;
ALTER TABLE companies ADD COLUMN duplicate_of_id INTEGER REFERENCES companies(id);

CREATE INDEX idx_companies_is_duplicate ON companies(is_duplicate);
```

## Monitoring

### Key Metrics

- **Auto-merge rate**: Percentage of new companies auto-merged
- **Candidate creation rate**: Candidates created per scraping job
- **Review rate**: Candidates reviewed per day
- **False positive rate**: Rejected candidates / total candidates

### Logs

All duplicate operations are logged with structured metadata:

```python
logger.info(
    "Duplicate merged",
    extra={
        "primary_id": 456,
        "duplicate_id": 789,
        "similarity": 0.97,
        "mode": "auto"
    }
)
```

### Job Statistics

Scraping jobs track duplicate-related stats in `job.stats`:

```json
{
  "auto_merged_duplicates": 5,
  "duplicate_candidates_created": 12
}
```

## Maintenance

### Manual Scan

Run a one-time scan via API or CLI:

```bash
# Via API (requires admin token)
curl -X POST https://api.example.com/api/v1/duplicates/scan \
  -H "Authorization: Bearer $TOKEN"

# Via CLI script
python scripts/maintenance/scan_duplicates.py --batch-size 100
```

### Cleanup

Manually trigger cleanup:

```bash
# Via RQ CLI
rq enqueue app.workers.scheduled_jobs.cleanup_old_duplicate_candidates_job

# Or wait for scheduled job (weekly)
```

### Tuning Thresholds

1. Start with default thresholds
2. Monitor false positive/negative rates
3. Adjust thresholds based on data quality:
   - High false positives → increase thresholds
   - High false negatives → decrease thresholds
4. Test in staging before applying to production

## Troubleshooting

### High False Positive Rate

**Symptoms:** Many rejected candidates

**Solutions:**
- Increase `DEDUPLICATOR_CANDIDATE_THRESHOLD`
- Increase field-specific thresholds
- Review data quality (inconsistent formatting)

### Missing Duplicates

**Symptoms:** Obvious duplicates not detected

**Solutions:**
- Decrease `DEDUPLICATOR_CANDIDATE_THRESHOLD`
- Check field-specific thresholds
- Verify real-time detection is enabled
- Run manual scan

### Performance Issues

**Symptoms:** Slow scraping or scans

**Solutions:**
- Increase `DEDUPLICATOR_SCAN_BATCH_SIZE`
- Disable real-time detection for bulk imports
- Schedule scans during off-peak hours
- Add database indexes

### Worker Not Processing Maintenance Queue

**Symptoms:** Scheduled jobs not running

**Solutions:**
- Verify worker command includes `maintenance` queue
- Check worker logs for errors
- Ensure `initialize_scheduled_jobs()` is called
- Verify Redis connection

## Best Practices

1. **Start conservative**: Use higher thresholds initially, then relax as needed
2. **Monitor regularly**: Review pending candidates weekly
3. **Test in staging**: Always test threshold changes in staging first
4. **Document decisions**: Add notes when rejecting candidates
5. **Backup before cleanup**: Ensure backups before running cleanup jobs
6. **Index properly**: Maintain database indexes for performance
7. **Use webhooks**: Integrate with external systems for notifications
8. **Review auto-merges**: Periodically audit auto-merged records

## See Also

- [API Documentation](../README.md#api-endpoints)
- [Deployment Guide](DEPLOYMENT.md)
- [Worker Configuration](DEPLOYMENT.md#worker-scheduler-setup)
