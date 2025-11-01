# 🚀 Production Deployment Guide

## 📋 Pre-Deployment Checklist

### ✅ Security

- [ ] Change `SECRET_KEY` to strong random value (min 32 chars)
- [ ] Change all default passwords (PostgreSQL, Redis, Tor)
- [ ] Set `DEBUG=False`
- [ ] Set `ENVIRONMENT=production`
- [ ] Configure `CORS_ORIGINS` with actual domain(s)
- [ ] Enable HTTPS/SSL certificates
- [ ] Review and restrict API rate limits
- [ ] Enable Sentry error tracking
- [ ] Set up firewall rules
- [ ] Disable unnecessary ports

### ✅ Database

- [ ] Use strong PostgreSQL password
- [ ] Enable PostgreSQL SSL connections
- [ ] Set up automated backups ✅ NEW
- [ ] Configure connection pooling ✅ NEW
- [ ] Test backup/restore procedures ✅ NEW
- [ ] Enable backup encryption ✅ NEW
- [ ] Configure cloud sync (S3) ✅ NEW
- [ ] Add database indexes for performance
- [ ] Set up read replicas (optional)

### ✅ Configuration

- [ ] Set proper `CORS_ORIGINS` (no wildcards!)
- [ ] Configure proper logging levels
- [ ] Set up log rotation
- [ ] Configure Sentry DSN
- [ ] Set proper rate limits
- [ ] Configure Redis password
- [ ] Set up monitoring

---

## 🔐 Secrets Management {#secrets-management}

### Overview

Modern deployments should avoid shipping long-lived secrets via `.env` files. KR Lead Scraper supports pulling configuration from managed secrets providers, reducing the blast radius of credential compromise and enabling centralized auditing. The application-level abstraction in `app/core/secrets_manager.py` works with AWS Secrets Manager and HashiCorp Vault. Use `.env` only for local development.

### Choosing a Provider

| Provider | Pros | Cons | Recommended for |
| --- | --- | --- | --- |
| AWS Secrets Manager | Fully managed, integrates with IAM, native CloudTrail auditing | AWS-specific, per-request cost | AWS-hosted infrastructure (ECS, EC2, Lambda) |
| HashiCorp Vault | Works across environments, rich policy model, dynamic credentials | Requires operating Vault, token lifecycle management | Hybrid/on-prem setups, teams already running Vault |

### AWS Secrets Manager Setup

1. Provision the secret:

   ```bash
   ./scripts/secrets/setup_aws_secrets.sh --secret-name kr-scraper/production --region eu-central-1 --create-policy
   ```

2. Attach the generated policy (or equivalent) to the compute role (EC2 or ECS task role):

   ```bash
   aws iam attach-role-policy --role-name kr-scraper-app --policy-arn arn:aws:iam::123456789012:policy/kr-scraper-production-read
   ```

3. Validate access:

   ```bash
   aws secretsmanager get-secret-value --region eu-central-1 --secret-id kr-scraper/production
   ```

4. Configure application environment variables:

   ```bash
   SECRETS_MANAGER=aws
   AWS_REGION=eu-central-1
   AWS_SECRETS_NAME=kr-scraper/production
   ```

### HashiCorp Vault Setup

1. Bootstrap the secret payload:

   ```bash
   ./scripts/secrets/setup_vault_secrets.sh --vault-addr https://vault.example.com --vault-path secret/data/kr-scraper
   ```

2. The script prints a read/list application token once. Store it securely. You can issue additional tokens with:

   ```bash
   vault token create -policy=kr-scraper-app -ttl=24h
   ```

3. Verify the stored payload:

   ```bash
   vault kv get secret/data/kr-scraper
   ```

4. Configure application environment variables:

   ```bash
   SECRETS_MANAGER=vault
   VAULT_ADDR=https://vault.example.com
   VAULT_TOKEN=<application-token>
   VAULT_PATH=secret/data/kr-scraper
   ```

### Secrets Rotation

- Manual rotation:

  ```bash
  python scripts/secrets/rotate_secrets.py --provider aws --secret-name kr-scraper/production --region eu-central-1 --backup
  ```

  Swap `--provider vault --vault-addr ... --vault-token ... --vault-path ...` when using Vault.

- Dry-run preview:

  ```bash
  python scripts/secrets/rotate_secrets.py --provider aws --secret-name kr-scraper/production --region eu-central-1 --dry-run --verbose
  ```

- Scheduled rotation: configure a cron job or systemd timer (e.g., every 90 days) invoking the rotation script with `--backup`.

### Backup and Disaster Recovery

- Set `BACKUP_ENCRYPTION_KEY` (Fernet key) before invoking `--backup`.
- Backups are written to `scripts/secrets/backups/` as encrypted JSON. Treat them as sensitive and store off-host.
- Restore workflow:

  ```bash
  python scripts/secrets/rotate_secrets.py --provider aws --rollback scripts/secrets/backups/secrets_backup_20251029_120000.json.enc --secret-name kr-scraper/production --region eu-central-1
  ```

  Restart dependent services after restoring secrets.

### Migration from `.env`

1. Run the appropriate setup script to seed the secrets manager.
2. Update deployment environment variables to include `SECRETS_MANAGER` and provider-specific settings.
3. Remove sensitive values from `.env` files and version control.
4. Redeploy the application; confirm secrets load via logs (look for "Loaded secrets" message).

### Monitoring & Auditing

- AWS: enable CloudTrail and configure alerts on `GetSecretValue` or `UpdateSecret` activity.
- Vault: enable audit devices (`vault audit enable file file_path=/var/log/vault_audit.log`) and review access patterns.

### Troubleshooting

<!-- markdownlint-disable MD032 MD034 -->

- **AWS `AccessDeniedException`:** ensure IAM role has `secretsmanager:GetSecretValue` and `DescribeSecret` for `AWS_SECRETS_NAME`.
- **Vault `permission denied`:** the application token must include `read` and `list` on `VAULT_PATH`.
- **`cryptography` import errors:** install dependencies via `pip install -r requirements.txt` before running rotation.
- **Missing Fernet key:** export `BACKUP_ENCRYPTION_KEY` before using `--backup` or `--rollback`.

### Security Best Practices

1. Rotate secrets at least every 90 days.
2. Use least-privilege roles/policies for secret access.
3. Maintain separate secret stores per environment (dev/staging/prod).
4. Encrypt backups at rest and restrict access.
5. Monitor access logs for anomalies and alert on unexpected reads.

Refer to `docs/PRODUCTION.md#secrets-management` from other guides for the latest operational details.

<!-- markdownlint-enable MD032 MD034 -->

---

## 🚀 Automated Deployment

### Overview

KR Lead Scraper verwendet automatisierte CI/CD-Pipelines für Deployments zu Staging und Production. Deployments werden via GitHub Actions getriggert und nutzen Blue-Green Deployment für Zero-Downtime.

### Quick Reference

**Deploy to Staging:**

```bash
git push origin develop
# Automatic deployment via GitHub Actions
```

**Deploy to Production:**

```bash
git tag v1.2.3
git push origin v1.2.3
# Automatic deployment via GitHub Actions
```

**Manual Rollback:**

- Gehe zu GitHub Actions → Rollback Workflow
- Workflow mit Environment und Target-Version starten

### Deployment Workflows

- **Staging**: Automatisch bei Push zu `develop` Branch
- **Production**: Automatisch bei Git Tag Push (Semantic Versioning)
- **Rollback**: Manuell via GitHub Actions oder automatisch bei Failures

### Deployment Strategy

- **Blue-Green Deployment** für Production (Zero-Downtime)
- **Rolling Deployment** für Staging (schneller)
- **Automatische Health-Checks** nach jedem Deployment
- **Automatischer Rollback** bei Health-Check-Failures

### Health Checks

**Multi-Layer Health Checks:**

1. Container Health (Docker Health Check)
2. API Health (`/health` endpoint)
3. Detailed Health (`/health/detailed` endpoint)
4. Smoke Tests (Authentication, Critical Endpoints)

**Configuration:**

- Production: 10 Retries, 30s Interval (max 5 Minuten)
- Staging: 5 Retries, 30s Interval (max 2.5 Minuten)

### Rollback Mechanism

**Automatischer Rollback:**

- Triggered bei Health-Check-Failures
- Switched Traffic zurück zu previous version
- Notification an Team

**Manueller Rollback:**

- Via GitHub Actions Rollback Workflow
- Requires: Environment, Target-Version, Reason
- Creates Incident Report

### Monitoring

- **GitHub Actions**: Deployment Logs und Status
- **Sentry**: Error Tracking mit Deployment-Context
- **Slack/Discord**: Deployment Notifications
- **Server Logs**: `/opt/kr-scraper/logs/deployment.log`

### Documentation

Für detaillierte Deployment-Dokumentation siehe:

- **[DEPLOYMENT.md](DEPLOYMENT.md)**: Umfassende Deployment-Anleitung
- **[scripts/deployment/README.md](../scripts/deployment/README.md)**: Deployment-Scripts-Dokumentation

### Deployment Checklist

**Before Deployment:**

- [ ] Tests passed locally
- [ ] Tested in Staging
- [ ] Reviewed CHANGELOG.md
- [ ] Team notified

**After Deployment:**

- [ ] Health checks passed
- [ ] Smoke tests passed
- [ ] Monitoring checked (Sentry)
- [ ] Team notified

---

## 🔐 Environment Variables for Production

### Critical Settings

```bash
# Environment
ENVIRONMENT=production
DEBUG=False

# Security & JWT
SECRET_KEY=<generate-strong-random-key-min-32-chars>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Database
DATABASE_URL=postgresql://kr_user:<strong-password>@db-host:5432/kr_leads
DB_ECHO=False

# Redis
REDIS_URL=redis://:<redis-password>@redis-host:6379
REDIS_DB=0

# CORS - IMPORTANT!
CORS_ORIGINS=https://your-domain.com,https://app.your-domain.com
CORS_ALLOW_CREDENTIALS=True
CORS_MAX_AGE=600

# API
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=False

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/kr-scraper/scraper.log

# Sentry Error Tracking
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_ENABLED=True
SENTRY_TRACES_SAMPLE_RATE=0.1  # 10% sampling in production
SENTRY_PROFILES_SAMPLE_RATE=0.1

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
```

### Generate Secure SECRET_KEY

```bash
# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# OpenSSL
openssl rand -base64 32
```

---

## ♻️ Connection Pooling

### Production Settings

```bash
DB_POOL_SIZE=20          # Base pool size
DB_MAX_OVERFLOW=40       # Total 60 connections
DB_POOL_TIMEOUT=30       # Seconds to wait for a connection
DB_POOL_RECYCLE=3600     # Recycle connections every hour
DB_CONNECT_TIMEOUT=10    # psycopg connect timeout (seconds)
DB_POOL_PRE_PING=True    # Validate connections before use
```

### Tuning Guidelines

- Ensure `DB_POOL_SIZE + DB_MAX_OVERFLOW` stays below PostgreSQL `max_connections`.
- Increase pool size for higher concurrency (e.g., 50/100 for heavy workloads).
- Lower `DB_POOL_RECYCLE` when behind proxies/load balancers with aggressive idle timeouts.
- Monitor live metrics via `app.database.database.get_pool_status()` and expose via health endpoints.

### Operational Notes

- Call `reset_connection_pool()` after database failovers or network incidents to rebuild the engine safely.
- Pool diagnostics are logged when `DB_ECHO=True` or via custom health endpoints.

---

## 💾 Database Backup & Recovery

Automated backups run on the maintenance RQ queue with daily, weekly, and monthly schedules. Each backup can be compressed, encrypted, uploaded to cloud storage, and verified by restoring to a temporary database.

### Environment Configuration

```bash
BACKUP_ENABLED=True

# Cron expressions (minute hour day month weekday)
BACKUP_DAILY_SCHEDULE="0 3 * * *"
BACKUP_WEEKLY_SCHEDULE="0 4 * * 0"
BACKUP_MONTHLY_SCHEDULE="0 5 1 * *"

# Retention policy (number of backups per tier)
BACKUP_RETENTION_DAILY=7
BACKUP_RETENTION_WEEKLY=4
BACKUP_RETENTION_MONTHLY=12

# Features
BACKUP_COMPRESSION_ENABLED=True
BACKUP_ENCRYPTION_ENABLED=True
BACKUP_ENCRYPTION_KEY=<GPG_KEY_ID>
BACKUP_CLOUD_SYNC_ENABLED=True
BACKUP_CLOUD_PROVIDER=s3
BACKUP_CLOUD_BUCKET=kr-scraper-backups-prod
BACKUP_VERIFICATION_ENABLED=True
```

### Manual Operations

```bash
# Trigger manual backup (compression + verification)
make backup-db

# Daily/weekly profiles with cleanup
make backup-daily
make backup-weekly

# List, verify, and restore backups
make backup-list
make backup-verify
make restore-db
make restore-test
```

Detailed runbook covering encryption, cloud sync, troubleshooting, and disaster recovery lives in [`docs/BACKUP.md`](BACKUP.md).

---

## 🤖 AI Model Configuration

### Environment Toggles

Aktiviere automatische Modellwahl und Prompt-Optimierung über `.env`:

```bash
OLLAMA_MODEL_SELECTION_ENABLED=true
OLLAMA_MODEL_PRIORITY=llama3.2,llama3.2:1b,mistral,qwen2.5
OLLAMA_MODEL_DEFAULT=llama3.2
PROMPT_OPTIMIZATION_ENABLED=true
```

- `OLLAMA_MODEL_SELECTION_ENABLED` – Schaltet den `ModelSelector` frei, der Benchmarks & Latenzen berücksichtigt.
- `OLLAMA_MODEL_PRIORITY` – Reihenfolge der Modelle für automatische Auswahl.
- `PROMPT_OPTIMIZATION_ENABLED` – Nutzt optimierte Prompts aus `data/prompts/optimized_prompts.json`.
- `OLLAMA_MODEL_DEFAULT` – Fallback-Modell, wenn Auswahl deaktiviert ist.

### Empfohlene Profile

| Workload                 | Einstellungen                                                                                  |
|--------------------------|-----------------------------------------------------------------------------------------------|
| Standard (balanced)      | `OLLAMA_MODEL_DEFAULT=llama3.2`, Selektion aktiv, Timeout 30s                                  |
| High-Volume / Fast       | `OLLAMA_MODEL_PRIORITY=llama3.2:1b,llama3.2,mistral,qwen2.5`, Timeout 20s, Batch-Größe reduzieren |
| Quality-Critical         | Selektion aktiv, Priorität `llama3.2,mistral`, Prompt-Optimierung aktiv, Timeout 45s           |
| Ressourcenlimitiert      | Selektion aktiv, Priorität `qwen2.5,llama3.2:1b`, Timeout 25s, `SMART_SCRAPER_MAX_SITES=5`     |

### Benchmarks & Reports

Nutze die Makefile-Targets zur regelmäßigen Aktualisierung der Leistungsdaten:

- `make benchmark-models` – Führt das Modell-Benchmarking gegen `data/benchmarks/test_cases.json` aus.
- `make benchmark-report` – Gibt `data/benchmarks/benchmark_report.md` aus (Markdown-Zusammenfassung).
- `make benchmark-prompts` – Optimiert Prompts und aktualisiert `data/prompts/optimized_prompts.json`.

Siehe [`docs/AI-SCRAPING.md#model-benchmarks-performance`](AI-SCRAPING.md#model-benchmarks-performance) für Details zu Metriken, Methodik und Ergebnissen.

### Produktionshinweise

1. Aktualisiere Benchmarks nach Modell-/Prompt-Updates (`make benchmark-models`).
2. Versioniere `data/benchmarks/ollama_results.json` und `data/prompts/optimized_prompts.json` für Reproduzierbarkeit.
3. Überwache Latenzen (p95/p99) in Grafana; passe Prioritäten bei Ausreißern an.
4. Hinterlege Modell- und Prompt-Variablen in Secrets Manager statt `.env` für Produktionsumgebungen.

---

## 🐳 Docker Compose Production

### docker-compose.prod.yml

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: kr-postgres-prod
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    ports:
      - "127.0.0.1:5432:5432"  # Only localhost
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: kr-redis-prod
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports:
      - "127.0.0.1:6379:6379"  # Only localhost
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build:
      context: .
      dockerfile: Dockerfile.prod
    container_name: kr-api-prod
    environment:
      - ENVIRONMENT=production
      - DEBUG=False
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "127.0.0.1:8000:8000"  # Only localhost (nginx proxy)
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    container_name: kr-nginx-prod
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./logs/nginx:/var/log/nginx
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

---

## 🌐 Nginx Configuration

### nginx/nginx.conf

```nginx
events {
    worker_connections 1024;
}

http {
    upstream api {
        server api:8000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req_status 429;

    # SSL Configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # HTTP -> HTTPS redirect
    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    # HTTPS Server
    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        # Security Headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;

        # API Proxy
        location / {
            limit_req zone=api_limit burst=20 nodelay;

            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # Health check (no rate limit)
        location /health {
            proxy_pass http://api;
            access_log off;
        }
    }
}
```

---

## 📦 Dockerfile.prod

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run migrations and start app
CMD alembic upgrade head && \
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 🔒 SSL/TLS Setup

### Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Auto-renewal (cron)
sudo certbot renew --dry-run
```

### Manual Certificate

```bash
# Generate self-signed (development only!)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout nginx/ssl/key.pem \
    -out nginx/ssl/cert.pem
```

---

## 📊 Monitoring & Logging

### Sentry Setup

1. Create account at https://sentry.io
2. Create new project
3. Copy DSN
4. Set in `.env`:

```bash
SENTRY_DSN=https://your-key@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_ENABLED=True
```

### Log Rotation

```bash
# /etc/logrotate.d/kr-scraper
/var/log/kr-scraper/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 appuser appuser
    sharedscripts
    postrotate
        docker-compose -f docker-compose.prod.yml restart api
    endscript
}
```

---

## 🔄 Deployment Steps

### 1. Initial Setup

```bash
# Clone repository
git clone https://github.com/tobiashaas/Lead-Scraper.git
cd Lead-Scraper

# Create production .env
cp .env.example .env
# Edit .env with production values!

# Create SSL directory
mkdir -p nginx/ssl

# Get SSL certificates (Let's Encrypt)
sudo certbot certonly --standalone -d your-domain.com
```

### 2. Database Setup

```bash
# Start database
docker-compose -f docker-compose.prod.yml up -d postgres redis

# Run migrations
docker-compose -f docker-compose.prod.yml run --rm api alembic upgrade head

# Create first user
docker-compose -f docker-compose.prod.yml run --rm api python -m app.scripts.create_user
```

### 3. Start Services

```bash
# Build and start all services
docker-compose -f docker-compose.prod.yml up -d --build

# Check logs
docker-compose -f docker-compose.prod.yml logs -f

# Check health
curl https://your-domain.com/health
```

### 4. Verify Deployment

```bash
# Test API
curl https://your-domain.com/docs

# Test authentication
curl -X POST https://your-domain.com/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"your-password"}'

# Check Sentry
# Trigger test error and verify in Sentry dashboard
```

---

## 🔄 Updates & Maintenance

### Update Application

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose -f docker-compose.prod.yml up -d --build

# Run new migrations
docker-compose -f docker-compose.prod.yml exec api alembic upgrade head
```

### Database Backup

```bash
# Manual backup
docker-compose -f docker-compose.prod.yml exec postgres \
    pg_dump -U kr_user kr_leads > backup_$(date +%Y%m%d).sql

# Automated backup (cron)
0 2 * * * /path/to/backup-script.sh
```

### Restore Database

```bash
# Restore from backup
docker-compose -f docker-compose.prod.yml exec -T postgres \
    psql -U kr_user kr_leads < backup_20250118.sql
```

---

## 🚨 Troubleshooting

### Check Logs

```bash
# API logs
docker-compose -f docker-compose.prod.yml logs -f api

# Nginx logs
docker-compose -f docker-compose.prod.yml logs -f nginx

# Database logs
docker-compose -f docker-compose.prod.yml logs -f postgres
```

### Common Issues

**CORS Errors:**
- Check `CORS_ORIGINS` in `.env`
- Verify frontend domain matches exactly
- Check nginx proxy headers

**Database Connection:**
- Verify `DATABASE_URL`
- Check PostgreSQL is running
- Test connection: `docker-compose exec postgres psql -U kr_user kr_leads`

**SSL Certificate:**
- Verify certificate paths in nginx.conf
- Check certificate expiration: `openssl x509 -in cert.pem -noout -dates`
- Renew Let's Encrypt: `sudo certbot renew`

---

## 📈 Performance Optimization

### Database Indexes

```sql
-- Add indexes for common queries
CREATE INDEX idx_companies_lead_status ON companies(lead_status);
CREATE INDEX idx_companies_lead_quality ON companies(lead_quality);
CREATE INDEX idx_companies_city ON companies(city);
CREATE INDEX idx_companies_created_at ON companies(created_at);
```

### Redis Caching

```python
# Enable Redis caching for expensive queries
# Configure in app/core/config.py
```

### Uvicorn Workers

```bash
# Increase workers based on CPU cores
# In Dockerfile.prod:
CMD uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 🔐 Security Best Practices

1. **Never commit secrets** to git
2. **Use strong passwords** (min 16 chars, random)
3. **Enable HTTPS** everywhere
4. **Restrict CORS** to specific domains
5. **Set up firewall** rules
6. **Regular updates** of dependencies
7. **Monitor logs** for suspicious activity
8. **Enable rate limiting**
9. **Use Sentry** for error tracking
10. **Regular backups**

---

## 📞 Support

- **Documentation:** https://github.com/tobiashaas/Lead-Scraper
- **Issues:** https://github.com/tobiashaas/Lead-Scraper/issues
- **Email:** t.haas@kunze-ritter.de
