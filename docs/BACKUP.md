# 💾 Database Backup & Recovery

## Overview

Automated database backup system ensures daily, weekly, and monthly protection with compression, optional encryption, cloud sync, and integrity verification. Backups run via RQ scheduler workers and can also be triggered manually with maintenance scripts or Makefile targets.

## Backup Strategy

### Backup Schedule

- **Daily**: 3 AM every day (retention: 7 days)
- **Weekly**: 4 AM every Sunday (retention: 4 weeks)
- **Monthly**: 5 AM on the 1st of each month (retention: 12 months)
- **Manual**: On demand via script or Makefile

### Retention Policy

Backups are kept according to tiered retention:

| Type    | Retention | Approximate Duration |
|---------|-----------|----------------------|
| Daily   | 7         | 1 week               |
| Weekly  | 4         | 1 month              |
| Monthly | 12        | 1 year               |

Retention cleanup runs after each backup and removes files beyond the configured limits.

### Backup Location

- **Primary**: `/backups` directory (Docker volume mount)
- **Optional Cloud Sync**: S3/GCS/Azure for off-site storage
- **Filename Pattern**: `backup_{type}_{YYYYMMDDTHHMMSSZ}.sql[.gz][.gpg]`

## Configuration

### Environment Variables

```bash
# Enable backups
BACKUP_ENABLED=True

# Schedules (cron format: minute hour day month weekday)
BACKUP_DAILY_SCHEDULE="0 3 * * *"
BACKUP_WEEKLY_SCHEDULE="0 4 * * 0"
BACKUP_MONTHLY_SCHEDULE="0 5 1 * *"

# Retention
BACKUP_RETENTION_DAILY=7
BACKUP_RETENTION_WEEKLY=4
BACKUP_RETENTION_MONTHLY=12

# Features
BACKUP_COMPRESSION_ENABLED=True   # Reduces size by 5-10x
BACKUP_ENCRYPTION_ENABLED=True    # GPG encryption for production
BACKUP_CLOUD_SYNC_ENABLED=True    # Cloud sync for disaster recovery
BACKUP_CLOUD_BUCKET=kr-scraper-backups-prod
BACKUP_VERIFICATION_ENABLED=True  # Weekly verification after backup
```

### Connection Pooling

```bash
# Production defaults
DB_POOL_SIZE=20          # Base pool size
DB_MAX_OVERFLOW=40       # Max overflow (total: 60 connections)
DB_POOL_TIMEOUT=30       # Max wait for connection (seconds)
DB_POOL_RECYCLE=3600     # Recycle connections after 1 hour
DB_CONNECT_TIMEOUT=10    # Connection timeout (seconds)
DB_POOL_PRE_PING=True    # Validate connections before use
```

**Guidance:**

- Small workload (<10 concurrent users): `pool_size=10`, `max_overflow=20`
- Medium workload (10-50 users): production defaults (20/40)
- Large workload (>50 users): consider `pool_size=50`, `max_overflow=100`
- Ensure `pool_size + max_overflow < PostgreSQL max_connections`

**Monitoring:**

```python
from app.database.database import get_pool_status
status = get_pool_status()
# => {"size": 20, "checked_in": 15, "checked_out": 5, "overflow": 2}
```

## Manual Backup

### Create Backup

```bash
# Via Makefile
make backup-db

# Script with options
python scripts/maintenance/backup_database.py --type manual --compress --verify

# Daily backup with automatic cleanup
python scripts/maintenance/backup_database.py --type daily --compress --cleanup

# Weekly backup with encryption
python scripts/maintenance/backup_database.py --type weekly --compress --encrypt --cleanup
```

### List Backups

```bash
make backup-list
# or
ls -lh /backups/*.sql*
```

### Verify Backup

```bash
make backup-verify
# or
python scripts/maintenance/backup_database.py --verify-only --backup-file /backups/backup_daily_20250118.sql.gz
```

## Restore Procedures

### Interactive Restore

```bash
make restore-db
# or
python scripts/maintenance/restore_database.py
```

Prompts for backup selection, confirms restore, terminates existing connections, and restarts application services.

### Restore Specific Backup

```bash
python scripts/maintenance/restore_database.py --backup-file /backups/backup_daily_20250118.sql.gz
```

### Test Restore (Non-Destructive)

```bash
make restore-test
# or
python scripts/maintenance/restore_database.py --backup-file /backups/backup_daily_20250118.sql.gz --test-only
```

### Force Restore (Use with caution)

```bash
python scripts/maintenance/restore_database.py --backup-file /backups/backup_daily_20250118.sql.gz --force
```

⚠️ Only use `--force` during emergency recovery when automation cannot confirm.

## Automated Backups

### RQ Scheduler

Workers launched with `--with-scheduler` register backup jobs:

| Job ID                        | Schedule         | Action                                    |
|------------------------------|------------------|-------------------------------------------|
| `database-backup-daily`      | `0 3 * * *`      | Daily compressed backup                   |
| `database-backup-weekly`     | `0 4 * * 0`      | Weekly backup (encryption recommended)    |
| `database-backup-monthly`    | `0 5 1 * *`      | Monthly archive                           |
| `database-backup-verification` | `0 6 * * 0`    | Weekly verification restore               |
| `database-backup-cleanup`    | `0 7 * * 0`      | Retention cleanup                         |

All jobs run on the `maintenance` queue.

### Monitoring

```bash
# Check scheduler/worker logs
docker logs kr-worker-prod-1 | grep backup

# List recent backup files
ls -lht /backups/ | head -n 10

# Check backup directory size
du -sh /backups/
```

### Cron Fallback (Optional)

Add to crontab (if RQ scheduler unavailable):

```bash
0 3 * * * /opt/kr-scraper/scripts/maintenance/backup_database.py --type daily --compress --cleanup
0 4 * * 0 /opt/kr-scraper/scripts/maintenance/backup_database.py --type weekly --compress --encrypt --cleanup
```

## Backup Verification

### Automated Verification

- Restores latest weekly backup to temporary database
- Runs table/row count validation queries
- Drops temporary database
- Emits webhook `backup.verified` or `backup.verification_failed`

### Manual Verification

```bash
python scripts/maintenance/backup_database.py --verify-only --backup-file /backups/backup_daily_20250118.sql.gz

python scripts/maintenance/restore_database.py --backup-file /backups/backup_daily_20250118.sql.gz --test-only
```

## Cloud Sync (Optional)

### AWS S3 Setup

1. Create S3 bucket (e.g., `kr-scraper-backups-prod`) with versioning and lifecycle policies.
2. Configure IAM role/service account with `s3:PutObject` and `s3:ListBucket`.
3. Set environment variables:

   ```bash
   BACKUP_CLOUD_SYNC_ENABLED=True
   BACKUP_CLOUD_PROVIDER=s3
   BACKUP_CLOUD_BUCKET=kr-scraper-backups-prod
   ```

4. Backups upload to `s3://<bucket>/backups/<filename>` after creation.

### Manual Sync

```bash
aws s3 sync /backups/ s3://kr-scraper-backups-prod/backups/ --exclude "*.tmp"
```

## Encryption

### Setup GPG Encryption

1. Generate key:

   ```bash
   gpg --gen-key
   ```

2. Retrieve key ID:

   ```bash
   gpg --list-keys
   ```

3. Configure environment:

   ```bash
   BACKUP_ENCRYPTION_ENABLED=True
   BACKUP_ENCRYPTION_KEY=<YOUR_KEY_ID>
   ```

4. Backups will be encrypted as `.gpg` files.

### Decrypt Backup

```bash
gpg --decrypt /backups/backup_daily_20250118.sql.gz.gpg > /backups/backup_daily_20250118.sql.gz
```

## Disaster Recovery

### Scenario 1: Recent Data Corruption (< 24h)

1. Stop apps: `docker-compose -f docker-compose.prod.yml stop app-blue app-green worker-1 worker-2`
2. Restore latest daily backup.
3. Verify critical data.
4. Restart apps: `docker-compose -f docker-compose.prod.yml start app-blue app-green worker-1 worker-2`

### Scenario 2: Accidental Deletion (Within Week)

Restore latest weekly backup. Expect up to 7 days of data loss.

### Scenario 3: Complete Database Loss

1. Download from S3: `aws s3 cp s3://kr-scraper-backups-prod/backups/backup_weekly_20250118.sql.gz /backups/`
2. Decrypt if necessary.
3. Run restore script.

### Scenario 4: Point-in-Time (Historical)

Use monthly archives closest to target date.

## Testing Backup & Restore

### Automated Tests

```bash
make test-backup-restore
# or
python scripts/maintenance/test_backup_restore.py --verbose
```

Tests cover:

- Backup creation & verification
- Compression/encryption integrity
- Restore to temporary database
- Retention policy cleanup
- Concurrent backup resilience

### Manual Checklist

1. `make backup-db`
2. `make restore-test`
3. `make backup-verify`

## Monitoring & Alerting

### Metrics

- Backup duration, size, success counts (exposed via logs/metrics)
- Monitor worker logs for entries tagged `backup`

### Alerts

- `backup.failed`: Trigger high-priority alert (email + Slack)
- `backup.verification_failed`: Critical alert
- Disk usage < 10 GB free: warning
- Cloud sync failures: warning

### Webhook Events

- `backup.completed`
- `backup.failed`
- `backup.verified`
- `backup.verification_failed`

## Best Practices

1. **Test restores monthly** using `make restore-test`.
2. **Enable cloud sync** for off-site backups.
3. **Encrypt production backups**; store keys securely.
4. **Monitor backup sizes** and investigate anomalies.
5. **Document recovery procedures** and train responders.
6. **Review retention policy** quarterly.
7. **Verify scheduler health** after deployments.

## Troubleshooting

| Issue | Resolution |
|-------|------------|
| Backup fails with "permission denied" | Check `/backups` permissions, ensure directory exists, confirm disk space |
| Backup file size is 0 | Inspect pg_dump logs, verify database connectivity |
| Restore fails with "database in use" | Stop application containers, terminate active sessions |
| Cloud sync fails | Validate AWS credentials, network access, bucket name |
| Verification fails | Confirm backup integrity, ensure temp database resources available |

## Disk Space Management

For a 1 GB database:

- Compressed backup ≈ 100-200 MB
- Daily backups: 7 × 200 MB = 1.4 GB
- Weekly backups: 4 × 200 MB = 0.8 GB
- Monthly backups: 12 × 200 MB = 2.4 GB
- **Total** ≈ 4.6 GB (recommend at least 10 GB free)

Monitor usage:

```bash
du -sh /backups/
df -h /backups/
ls -lhS /backups/ | head -n 10
```

## Examples

### Enable Automated Backups

```bash
# In .env
BACKUP_ENABLED=True
BACKUP_COMPRESSION_ENABLED=True
BACKUP_VERIFICATION_ENABLED=True

# Restart worker with scheduler
docker-compose restart worker-1
```

### Manual Backup Before Deployment

```bash
make backup-db
```

### Direct Restore

```bash
python scripts/maintenance/restore_database.py --backup-file /backups/backup_daily_20250118.sql.gz
```

### Enable Cloud Sync to S3

```bash
BACKUP_CLOUD_SYNC_ENABLED=True
BACKUP_CLOUD_PROVIDER=s3
BACKUP_CLOUD_BUCKET=kr-scraper-backups-prod
```

Backups automatically upload after creation.
