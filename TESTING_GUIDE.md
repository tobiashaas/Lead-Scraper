# 🧪 Testing Guide - KR Lead Scraper

## 🚀 Quick Start - System testen

### 1. Setup (falls noch nicht gemacht)

```bash
# Virtual Environment erstellen
python -m venv venv

# Aktivieren (Windows)
venv\Scripts\activate

# Dependencies installieren
pip install -r requirements.txt

# Playwright Browser installieren
playwright install chromium

# Environment Variables setzen
cp .env.example .env
# Dann .env bearbeiten mit deinen Settings
```

### 2. Database Setup

```bash
# PostgreSQL starten (Docker)
docker-compose up -d postgres redis

# Oder lokal installiert:
# Erstelle Database: kr_leads

# Migrations ausführen
alembic upgrade head

# Test-User erstellen (optional)
python scripts/create_test_user.py
```

### 3. API Server starten

```bash
# Development Server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Oder mit Docker
docker-compose up
```

**API läuft auf:** http://localhost:8000

**Swagger Docs:** http://localhost:8000/docs

**ReDoc:** http://localhost:8000/redoc

---

## 🧪 Test-Szenarien

### ✅ Test 1: Health Check

```bash
curl http://localhost:8000/health
```

**Erwartete Antwort:**
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

---

### ✅ Test 2: API Authentication

#### 2.1 User registrieren

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "SecurePassword123!"
  }'
```

#### 2.2 Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "SecurePassword123!"
  }'
```

**Kopiere den `access_token` aus der Antwort!**

#### 2.3 Geschützte Route testen

```bash
# Ersetze YOUR_TOKEN mit dem access_token
curl http://localhost:8000/api/v1/companies/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### ✅ Test 3: Company Management

#### 3.1 Company erstellen

```bash
curl -X POST http://localhost:8000/api/v1/companies/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test GmbH",
    "city": "Stuttgart",
    "street": "Hauptstraße 1",
    "postal_code": "70173",
    "phone": "+49 711 123456",
    "email": "info@test-gmbh.de",
    "website": "https://test-gmbh.de",
    "industry": "IT-Dienstleistungen",
    "lead_status": "new",
    "lead_quality": "high"
  }'
```

#### 3.2 Companies auflisten

```bash
curl http://localhost:8000/api/v1/companies/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 3.3 Company suchen

```bash
curl "http://localhost:8000/api/v1/companies/?search=Test" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 3.4 Company nach ID abrufen

```bash
# Ersetze 1 mit der ID aus der Antwort
curl http://localhost:8000/api/v1/companies/1 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 3.5 Company updaten

```bash
curl -X PUT http://localhost:8000/api/v1/companies/1 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "lead_status": "contacted",
    "lead_quality": "very_high"
  }'
```

---

### ✅ Test 4: Scraping Job

#### 4.1 Scraping Job starten

```bash
curl -X POST http://localhost:8000/api/v1/scraping/jobs \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "gelbeseiten",
    "search_term": "IT Dienstleistungen",
    "location": "Stuttgart",
    "max_results": 10
  }'
```

**Kopiere die `job_id` aus der Antwort!**

#### 4.2 Job Status prüfen

```bash
# Ersetze JOB_ID mit der job_id
curl http://localhost:8000/api/v1/scraping/jobs/JOB_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 4.3 Alle Jobs auflisten

```bash
curl http://localhost:8000/api/v1/scraping/jobs \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### ✅ Test 5: Statistics & Analytics

```bash
curl http://localhost:8000/api/v1/companies/stats/overview \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 🧪 Automatisierte Tests ausführen

### Alle Tests

```bash
pytest tests/ -v
```

### Nur Unit Tests

```bash
pytest tests/unit/ -v
```

### Nur Integration Tests

```bash
pytest tests/integration/ -v
```

### Mit Coverage

```bash
pytest tests/ -v --cov=app --cov-report=html
```

**Coverage Report:** `htmlcov/index.html`

### Spezifische Tests

```bash
# Nur API Tests
pytest tests/integration/test_api_companies.py -v

# Nur Scraper Tests
pytest tests/unit/test_scrapers.py -v

# Nur Auth Tests
pytest tests/integration/test_api_auth.py -v
```

---

## 🐛 Debugging

### Logs anschauen

```bash
# Application Logs
tail -f logs/app.log

# Error Logs
tail -f logs/error.log
```

### Database inspizieren

```bash
# PostgreSQL Shell
docker exec -it kr-lead-scraper-postgres psql -U postgres -d kr_leads

# Oder lokal
psql -U postgres -d kr_leads

# Nützliche Queries:
SELECT COUNT(*) FROM companies;
SELECT * FROM companies LIMIT 10;
SELECT * FROM scraping_jobs ORDER BY created_at DESC LIMIT 5;
```

### Redis inspizieren

```bash
# Redis CLI
docker exec -it kr-lead-scraper-redis redis-cli

# Oder lokal
redis-cli

# Nützliche Commands:
KEYS *
GET rate_limit:*
```

---

## 📊 Performance Testing

### Load Test mit Apache Bench

```bash
# 100 Requests, 10 concurrent
ab -n 100 -c 10 -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/companies/
```

### Load Test mit wrk

```bash
# 30 Sekunden, 10 Threads, 100 Connections
wrk -t10 -c100 -d30s \
  -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/companies/
```

---

## 🎯 Test Checkliste

### ✅ Basis-Funktionalität
- [ ] API Server startet ohne Fehler
- [ ] Health Check ist grün
- [ ] Database Connection funktioniert
- [ ] Redis Connection funktioniert

### ✅ Authentication
- [ ] User Registration funktioniert
- [ ] Login funktioniert
- [ ] JWT Token wird generiert
- [ ] Geschützte Routes erfordern Token
- [ ] Ungültige Tokens werden abgelehnt

### ✅ Company Management
- [ ] Company erstellen funktioniert
- [ ] Companies auflisten funktioniert
- [ ] Company suchen funktioniert
- [ ] Company updaten funktioniert
- [ ] Company löschen funktioniert (soft delete)
- [ ] Validation funktioniert (ungültige Daten werden abgelehnt)

### ✅ Scraping
- [ ] Scraping Job kann gestartet werden
- [ ] Job Status kann abgerufen werden
- [ ] Jobs werden in Database gespeichert
- [ ] Scraping Results werden gespeichert
- [ ] Duplicate Detection funktioniert

### ✅ Data Quality
- [ ] Email Validation funktioniert
- [ ] Phone Number Normalization funktioniert
- [ ] Website Validation funktioniert
- [ ] Duplicate Detection funktioniert

### ✅ Performance
- [ ] API Response Time < 200ms (ohne Scraping)
- [ ] Database Queries sind optimiert
- [ ] Rate Limiting funktioniert
- [ ] Caching funktioniert (wenn implementiert)

---

## 🚀 Production Readiness Check

### ✅ Code Quality
- [x] Alle Tests passing (99/99) ✅
- [x] Code Coverage > 80% ✅
- [x] Black Formatting ✅
- [x] Ruff Linting ✅
- [x] Type Checking (mypy) ✅

### ✅ Security
- [x] JWT Authentication ✅
- [x] Rate Limiting ✅
- [x] Input Validation ✅
- [x] SQL Injection Prevention ✅
- [x] Security Scan (Bandit) ✅

### ✅ DevOps
- [x] Docker Build ✅
- [x] CI/CD Pipeline ✅
- [x] Branch Protection ✅
- [ ] Production Deployment
- [ ] Monitoring Setup

### ✅ Documentation
- [x] README ✅
- [x] API Docs (Swagger) ✅
- [x] Testing Guide ✅
- [ ] User Guide
- [ ] Deployment Guide

---

## 🎉 Happy Testing!

**Bei Problemen:**
1. Check die Logs (`logs/app.log`)
2. Check die Database Connection
3. Check die Environment Variables (`.env`)
4. Erstelle ein Issue auf GitHub

**Viel Erfolg beim Testen!** 🚀
