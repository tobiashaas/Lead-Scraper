# 🔧 Environment Setup Guide

## 📋 Deine `.env` Konfiguration

Kopiere diese Werte in deine `.env` Datei:

```bash
# ============================================
# DATABASE CONFIGURATION
# ============================================
# Für lokale Entwicklung mit Docker
DATABASE_URL=postgresql://kr_user:SecurePassword123!@localhost:5432/kr_leads
DB_ECHO=False

# PostgreSQL Credentials (für docker-compose)
POSTGRES_DB=kr_leads
POSTGRES_USER=kr_user
POSTGRES_PASSWORD=SecurePassword123!

# ============================================
# REDIS CONFIGURATION
# ============================================
REDIS_URL=redis://localhost:6379
REDIS_DB=0

# ============================================
# TOR CONFIGURATION (Optional)
# ============================================
TOR_ENABLED=False  # Auf True setzen wenn Tor läuft
TOR_PROXY=socks5://127.0.0.1:9050
TOR_CONTROL_PORT=9051
TOR_CONTROL_PASSWORD=  # Leer lassen wenn kein Password

# ============================================
# SCRAPING CONFIGURATION
# ============================================
SCRAPING_DELAY_MIN=3
SCRAPING_DELAY_MAX=8
MAX_RETRIES=3
REQUEST_TIMEOUT=30

# ============================================
# RATE LIMITING
# ============================================
RATE_LIMIT_REQUESTS=10
RATE_LIMIT_WINDOW=60

# ============================================
# PLAYWRIGHT CONFIGURATION
# ============================================
PLAYWRIGHT_HEADLESS=True
PLAYWRIGHT_BROWSER=chromium

# ============================================
# GOOGLE PLACES API (Optional)
# ============================================
# WICHTIG: Niemals den echten Key in Git committen!
# Hole dir einen Key: https://console.cloud.google.com/apis/credentials
GOOGLE_PLACES_API_KEY=

# ============================================
# API CONFIGURATION
# ============================================
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=True

# ============================================
# JWT AUTHENTICATION
# ============================================
# WICHTIG: Ändere diesen Secret in Production!
SECRET_KEY=your-super-secret-jwt-key-change-in-production-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# ============================================
# LOGGING
# ============================================
LOG_LEVEL=INFO
LOG_FILE=logs/scraper.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5

# ============================================
# OLLAMA CONFIGURATION (Lokal AI)
# ============================================
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2
OLLAMA_TIMEOUT=120

# ============================================
# CRAWL4AI CONFIGURATION
# ============================================
CRAWL4AI_ENABLED=True
CRAWL4AI_WORD_COUNT_THRESHOLD=10
CRAWL4AI_MAX_RETRIES=3

# ============================================
# SENTRY (Error Tracking - Optional)
# ============================================
# SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
# SENTRY_ENVIRONMENT=development

# ============================================
# DEVELOPMENT
# ============================================
DEBUG=True
ENVIRONMENT=development
```

---

## 🐳 Docker Compose Setup

### 1. Services starten

```bash
# Alle Services starten
docker-compose up -d

# Nur Database & Redis
docker-compose up -d postgres redis

# Logs anschauen
docker-compose logs -f
```

### 2. Services prüfen

```bash
# Status
docker-compose ps

# PostgreSQL testen
docker exec -it kr-lead-scraper-postgres psql -U kr_user -d kr_leads -c "SELECT version();"

# Redis testen
docker exec -it kr-lead-scraper-redis redis-cli ping
```

---

## 🔑 Wichtige Credentials

### PostgreSQL (lokal mit Docker)
- **Host:** `localhost`
- **Port:** `5432`
- **Database:** `kr_leads`
- **User:** `kr_user`
- **Password:** `SecurePassword123!` (ändere das!)

**Connection String:**
```
postgresql://kr_user:SecurePassword123!@localhost:5432/kr_leads
```

### Redis (lokal mit Docker)
- **Host:** `localhost`
- **Port:** `6379`
- **Database:** `0`
- **Password:** (kein Password)

**Connection String:**
```
redis://localhost:6379
```

### API
- **URL:** `http://localhost:8000`
- **Docs:** `http://localhost:8000/docs`
- **Health:** `http://localhost:8000/health`

---

## 🔒 Security Best Practices

### ⚠️ NIEMALS committen:
- ❌ `.env` Datei
- ❌ API Keys
- ❌ Passwords
- ❌ JWT Secrets
- ❌ Database Credentials
- ❌ Debug HTML Files (können Keys enthalten!)

### ✅ Immer verwenden:
- ✅ `.env.example` für Dokumentation
- ✅ Environment Variables für Secrets
- ✅ `.gitignore` für sensitive Files
- ✅ Starke Passwords in Production
- ✅ Unterschiedliche Secrets für Dev/Staging/Prod

---

## 🚀 Quick Start

### 1. Environment kopieren
```bash
cp .env.example .env
```

### 2. `.env` bearbeiten
- Setze `POSTGRES_PASSWORD`
- Setze `SECRET_KEY` (min. 32 Zeichen)
- Optional: `GOOGLE_PLACES_API_KEY`

### 3. Docker starten
```bash
docker-compose up -d postgres redis
```

### 4. Database migrieren
```bash
alembic upgrade head
```

### 5. API starten
```bash
uvicorn app.main:app --reload
```

### 6. Testen
```bash
curl http://localhost:8000/health
```

---

## 🔧 Troubleshooting

### Database Connection Error
```bash
# Check ob PostgreSQL läuft
docker-compose ps postgres

# Logs anschauen
docker-compose logs postgres

# Neu starten
docker-compose restart postgres
```

### Redis Connection Error
```bash
# Check ob Redis läuft
docker-compose ps redis

# Logs anschauen
docker-compose logs redis

# Neu starten
docker-compose restart redis
```

### Port bereits belegt
```bash
# PostgreSQL Port 5432
netstat -ano | findstr :5432

# Redis Port 6379
netstat -ano | findstr :6379

# API Port 8000
netstat -ano | findstr :8000
```

---

## 📝 Production Checklist

Vor Production Deployment:

- [ ] `DEBUG=False` setzen
- [ ] `ENVIRONMENT=production` setzen
- [ ] Starkes `SECRET_KEY` generieren (min. 32 Zeichen)
- [ ] Starkes `POSTGRES_PASSWORD` setzen
- [ ] `PLAYWRIGHT_HEADLESS=True` setzen
- [ ] `API_RELOAD=False` setzen
- [ ] Sentry DSN konfigurieren
- [ ] CORS Settings prüfen
- [ ] Rate Limits anpassen
- [ ] Backup Strategy implementieren
- [ ] Monitoring Setup
- [ ] SSL/TLS Zertifikate

---

## 🎉 Fertig!

Deine lokale Entwicklungsumgebung ist jetzt bereit!

**Nächste Schritte:**
1. Folge dem `TESTING_GUIDE.md`
2. Teste die API Endpoints
3. Starte einen Scraping Job
4. Check die Logs

**Bei Problemen:**
- Check die Logs: `docker-compose logs`
- Check die `.env` Datei
- Check ob alle Services laufen: `docker-compose ps`
