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
- [ ] Set up automated backups
- [ ] Configure connection pooling
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
