# 📋 TODO - KR Lead Scraper

## 🔴 Kritisch (Vor Production)

### Testing
- [x] Unit Tests für alle Scraper schreiben (99 Tests, 100% Pass Rate) ✅
- [x] Integration Tests für API Endpoints ✅
- [x] Tests für Data Processors (Validator, Normalizer, Deduplicator) ✅
- [ ] Tests für Crawl4AI + Ollama Integration
- [ ] End-to-End Tests für komplette Pipeline
- [ ] Load Testing für API
- [x] Test Coverage auf min. 80% erhöhen (Scraper & Validator Module) ✅

### Sicherheit
- [x] API Authentication implementieren (JWT) ✅
- [x] Rate Limiting für API Endpoints ✅
- [x] Input Validation für alle Endpoints ✅
- [x] SQL Injection Prevention überprüfen (SQLAlchemy ORM) ✅
- [x] CORS Konfiguration für Production ✅
- [ ] Secrets Management (z.B. AWS Secrets Manager)
- [x] Security Audit durchführen (Bandit, alle Workflows grün) ✅

### Database
- [x] Erste Alembic Migration erstellen (`make db-migrate`)
- [x] psycopg3 Integration (SQLAlchemy 2.0+)
- [x] Indizes für häufige Queries optimieren ✅
- [ ] Database Backup Strategy implementieren
- [ ] Connection Pooling testen
- [ ] Query Performance optimieren

### Monitoring & Logging
- [x] Structured Logging implementieren (JSON) ✅
- [x] Error Tracking (Sentry Integration) ✅
- [ ] Metrics Collection (Prometheus)
- [ ] Grafana Dashboards erstellen
- [ ] Alerting Setup (Email/Slack)
- [ ] Log Rotation konfigurieren

### CI/CD & DevOps
- [x] GitHub Actions Workflows (Tests, Code Quality, Security) ✅
- [x] Docker Build Pipeline ✅
- [x] Branch Protection Rules ✅
- [x] Python 3.13 Kompatibilität ✅
- [x] Code Quality Tools (Black, Ruff, isort, mypy) ✅
- [ ] Production Deployment Pipeline
- [ ] Staging Environment Setup

## 🟡 Wichtig (Nächste 2 Wochen)

### API Features
- [ ] Pagination für alle List-Endpoints testen
- [ ] Filtering & Sorting verbessern
- [x] Bulk Operations (Bulk Update, Bulk Delete) ✅
- [x] Export Endpoints (CSV, JSON) ✅
- [x] Webhook Support für Job Completion ✅
- [ ] API Versioning Strategy
- [ ] API Documentation verbessern

### Scraping
- [ ] Alle Scraper mit neuen Processors integrieren
- [ ] Smart Scraper in Pipeline integrieren
- [ ] Scraping Job Queue implementieren (Celery/RQ)
- [ ] Retry Logic für failed Jobs
- [ ] Scraping Statistics Dashboard
- [ ] Rate Limiting pro Source
- [ ] CAPTCHA Handling verbessern

### Data Quality
- [x] Lead Scoring Algorithmus implementieren ✅
- [ ] Duplicate Detection automatisieren
- [ ] Data Enrichment Pipeline
- [ ] Email Verification Service
- [ ] Phone Number Validation verbessern
- [ ] Website Availability Check
- [ ] Company Size Estimation

### AI/ML Features
- [ ] Ollama Models benchmarken (llama3.2 vs mistral vs qwen2.5)
- [ ] Prompt Engineering optimieren
- [ ] Extraction Accuracy messen
- [ ] Fine-tuning für Business-Daten evaluieren
- [ ] Fallback-Strategien testen
- [ ] AI Response Caching

## 🟢 Nice-to-Have (Später)

### Frontend
- [ ] Admin Dashboard (React/Vue)
- [ ] Company Management UI
- [ ] Scraping Job Management UI
- [ ] Statistics & Analytics Dashboard
- [ ] Export/Import UI
- [ ] User Management

### Integrations
- [ ] SmartWe CRM Integration
- [ ] HubSpot Integration
- [ ] Salesforce Integration
- [ ] Email Marketing Tools (Mailchimp, SendGrid)
- [ ] Slack Notifications
- [ ] Zapier Integration

### Advanced Features
- [ ] Multi-Tenancy Support
- [ ] User Roles & Permissions
- [ ] Audit Log
- [ ] Scheduled Scraping Jobs (Cron)
- [ ] Real-time Scraping Status (WebSockets)
- [ ] Advanced Search (Elasticsearch)
- [ ] GraphQL API

### Performance
- [ ] Caching Strategy (Redis)
- [ ] Database Query Optimization
- [ ] Async Processing für lange Tasks
- [ ] CDN für Static Assets
- [ ] Database Sharding evaluieren
- [ ] Read Replicas für Reporting

### Documentation
- [ ] API Documentation (OpenAPI/Swagger)
- [ ] Architecture Documentation
- [ ] Deployment Guide
- [ ] User Manual
- [ ] Contributing Guidelines
- [ ] Code Comments verbessern

## 🧪 Testing Checklist

### Sofort testen
- [ ] `make setup` - Komplettes Setup
- [ ] `make docker-up` - Docker Services starten
- [ ] `make ollama-setup` - Ollama Models installieren
- [ ] `make db-init` - Database initialisieren
- [ ] `make run` - API starten
- [ ] `make health` - Health Check
- [ ] API Endpoints manuell testen (Swagger UI)

### Scraper testen
- [ ] 11880 Scraper mit echten Daten
- [ ] Gelbe Seiten Scraper
- [ ] Das Örtliche Scraper
- [ ] GoYellow Scraper
- [ ] Handelsregister Scraper
- [ ] Google Places Integration
- [ ] Smart Scraper mit verschiedenen Websites

### AI Features testen
- [ ] Crawl4AI Extraktion Qualität
- [ ] Ollama Response Zeit
- [ ] Verschiedene Models vergleichen
- [ ] Fallback-Mechanismen
- [ ] Error Handling

### Data Processing testen
- [ ] Email Validation
- [ ] Phone Number Normalization
- [ ] Website URL Cleaning
- [ ] Company Name Normalization
- [ ] Duplicate Detection
- [ ] Merge Logic

### Performance testen
- [ ] API Response Times
- [ ] Database Query Performance
- [ ] Concurrent Scraping Jobs
- [ ] Memory Usage
- [ ] Docker Container Resources

## 📦 Deployment Checklist

### Pre-Deployment
- [ ] Alle Tests grün
- [ ] Code Review durchgeführt
- [ ] Security Scan bestanden
- [ ] Performance Tests OK
- [ ] Database Backup erstellt
- [ ] Rollback Plan dokumentiert

### Production Setup
- [ ] VPS/Cloud Server provisionen
- [ ] Domain & SSL Zertifikat
- [ ] Firewall Regeln
- [ ] Monitoring Setup
- [ ] Backup Strategy
- [ ] CI/CD Pipeline testen

### Post-Deployment
- [ ] Health Checks verifizieren
- [ ] Logs überprüfen
- [ ] Performance Monitoring
- [ ] Error Tracking
- [ ] User Acceptance Testing

## 🐛 Known Issues

### Zu beheben
- [ ] Markdown Linting Warnings in README.md
- [ ] MyPy Type Hints vervollständigen
- [ ] Playwright Browser Download in Docker optimieren
- [ ] Redis Password in Production Docker Compose
- [ ] Nginx Config für Production erstellen

### Zu evaluieren
- [ ] Crawl4AI vs. Trafilatura Performance
- [ ] Ollama Model Size vs. Quality Trade-off
- [ ] Tor Network Stability
- [ ] Rate Limiting Thresholds
- [ ] Database Connection Pool Size

## 📚 Dokumentation TODO

- [ ] README.md vervollständigen
- [ ] API Dokumentation (Swagger erweitern)
- [ ] Deployment Guide schreiben
- [ ] Scraper Configuration Guide
- [ ] Troubleshooting Guide
- [ ] FAQ erstellen
- [ ] Video Tutorials (optional)

## 🔄 Refactoring

- [ ] Scraper Base Class erweitern
- [ ] Error Handling vereinheitlichen
- [ ] Logging konsistent machen
- [ ] Config Management verbessern
- [ ] Code Duplikation reduzieren
- [ ] Type Hints vervollständigen

## 💡 Ideen für Zukunft

- [ ] Machine Learning für Lead Scoring
- [ ] Automatische Lead Kategorisierung
- [ ] Sentiment Analysis von Reviews
- [ ] Competitive Intelligence Features
- [ ] Market Analysis Dashboard
- [ ] Predictive Lead Scoring
- [ ] A/B Testing für Scraping Strategies

---

## 📊 Progress Tracking

**Gesamt Fortschritt: ~45%**

- ✅ Infrastructure & Setup (100%)
- ✅ Database Models (100%)
- ✅ Database Migration (100%) ⭐ NEW
- ✅ API Endpoints (100%)
- ✅ Data Processors (100%)
- ✅ AI Integration (100%)
- ✅ Unit Testing (85%) ⭐ NEW - 47 Tests, 100% Pass Rate
- ⏳ Integration Testing (0%)
- ⏳ Security (30%)
- ⏳ Monitoring (20%)
- ⏳ Documentation (50%)
- ⏳ Production Deployment (0%)

---

## 🎉 HEUTE FERTIG (20.10.2025) - Alle High Priority Features!

### ✅ Phase 1: Backend Features (KOMPLETT)

**1. Webhook Delivery System**
- ✅ HMAC-SHA256 Signaturen für Sicherheit
- ✅ Retry Logic mit Exponential Backoff (1s, 2s, 4s)
- ✅ Async HTTP Delivery (blockiert API nicht)
- ✅ 3 Events: `job.started`, `job.completed`, `job.failed`
- ✅ Detailliertes Logging & Error Handling
- **Dateien:** `app/utils/webhook_delivery.py`, `app/utils/webhook_helpers.py`
- **Integration:** In `app/api/scraping.py` integriert

**2. Company Deduplicator**
- ✅ 3 Detection Strategies:
  - Exact phone match (100% confidence)
  - Exact website match (95% confidence)
  - Fuzzy name + city matching (85%+ confidence)
- ✅ Smart Merging (keep primary, fill missing fields)
- ✅ Auto-deduplication nach Scraping (95% threshold)
- ✅ API Endpoints: find duplicates, merge, scan all
- ✅ Dry-run mode für sicheres Testen
- **Dateien:** `app/utils/deduplicator.py`, `app/api/deduplication.py`
- **API Endpoints:**
  - `GET /api/v1/deduplication/companies/{id}/duplicates`
  - `POST /api/v1/deduplication/merge`
  - `POST /api/v1/deduplication/scan`

**3. Alle 6 Scraper aktiviert**
- ✅ 11880.com
- ✅ Gelbe Seiten
- ✅ Das Örtliche
- ✅ GoYellow
- ✅ Unternehmensverzeichnis
- ✅ Handelsregister
- **Datei:** `app/api/scraping.py` - Alle Scraper sind jetzt über API verfügbar

### ✅ Phase 2: Dashboard Frontend (KOMPLETT)

**4. React Dashboard mit TypeScript + Vite**
- ✅ **Login Page** - JWT Authentication
- ✅ **Dashboard** - Übersicht mit Statistiken & Quick Actions
- ✅ **Scraping Page** - Stadt/PLZ eingeben & Scraper starten! 🎯
- ✅ **Companies Page** - Alle Firmen mit Suche, Filter & Pagination

**Features:**
- ✅ Live Job Monitoring (auto-refresh alle 5 Sekunden)
- ✅ 6 Scraper-Quellen Auswahl
- ✅ Responsive Design mit TailwindCSS
- ✅ Lead Quality Badges (A, B, C, D)
- ✅ Pagination für Company List
- ✅ Real-time Status Updates

**Tech Stack:**
- React 18 + TypeScript
- Vite (schneller Build)
- TailwindCSS (Styling)
- React Query (TanStack Query) - API State Management
- React Router - Navigation
- Axios - HTTP Client
- Lucide Icons

**Dateien:**
- `frontend/src/pages/Login.tsx`
- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/pages/Scraping.tsx` - **HAUPTFEATURE: Stadt/PLZ Input!**
- `frontend/src/pages/Companies.tsx`
- `frontend/src/lib/api.ts` - API Client
- `frontend/src/App.tsx` - Routing

---

## 🚀 MORGEN STARTEN (21.10.2025)

### Schritt 1: Repository pullen
```bash
cd /Users/tobiashaas/Desktop/Lead-Scraper
git pull origin fix/config-extra-fields
```

### Schritt 2: Backend starten
```bash
# Docker Services starten (PostgreSQL, Redis, Ollama)
docker-compose up -d

# Warten bis Services ready sind (ca. 30 Sekunden)
sleep 30

# API starten
make run
# ODER
uvicorn app.main:app --reload
```

**Backend läuft auf:** `http://localhost:8000`
**API Docs:** `http://localhost:8000/docs`

### Schritt 3: Frontend starten
```bash
cd frontend

# Dependencies installieren (nur beim ersten Mal)
npm install

# Dev Server starten
npm run dev
```

**Frontend läuft auf:** `http://localhost:5173`

### Schritt 4: Testen!

**1. Login:**
- Öffne `http://localhost:5173`
- Login mit deinem User (oder erstelle einen via API)

**2. Dashboard:**
- Siehst du die Statistiken?
- Funktionieren die Quick Action Buttons?

**3. Scraping Page (HAUPTFEATURE!):**
- Klicke auf "Neuen Scraping-Job starten"
- **Stadt/PLZ eingeben:** z.B. "Stuttgart" oder "70173"
- **Branche eingeben:** z.B. "IT", "Handwerk", "Gastronomie"
- **Quelle wählen:** z.B. "11880.com"
- **Max. Seiten:** z.B. 5
- **Klick auf "Scraping starten"**
- Beobachte die Job-Tabelle unten - sie aktualisiert sich automatisch alle 5 Sekunden!

**4. Companies Page:**
- Siehst du die gescrapten Firmen?
- Funktioniert die Suche?
- Funktioniert die Pagination?

### Schritt 5: Features testen

**Webhook Delivery:**
```bash
# Webhook erstellen (via API Docs oder curl)
curl -X POST "http://localhost:8000/api/v1/webhooks" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://webhook.site/YOUR-UNIQUE-URL",
    "events": ["job.completed", "job.failed"],
    "secret": "my-secret-key",
    "active": true
  }'

# Dann Scraping Job starten und Webhook wird getriggert!
```

**Deduplication:**
```bash
# Duplikate scannen (dry-run)
curl -X POST "http://localhost:8000/api/v1/deduplication/scan?dry_run=true" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Duplikate für eine Firma finden
curl "http://localhost:8000/api/v1/deduplication/companies/123/duplicates" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 📝 Was zu testen ist:

### ✅ Checklist für morgen:

**Backend:**
- [ ] API startet ohne Fehler
- [ ] Alle 6 Scraper funktionieren
- [ ] Webhook Delivery funktioniert
- [ ] Deduplication funktioniert
- [ ] Auto-Dedup nach Scraping läuft

**Frontend:**
- [ ] Login funktioniert
- [ ] Dashboard zeigt Statistiken
- [ ] Scraping Page: Stadt/PLZ Input funktioniert
- [ ] Scraping Job startet erfolgreich
- [ ] Live Job Monitoring funktioniert (5s refresh)
- [ ] Companies Page zeigt Firmen
- [ ] Suche funktioniert
- [ ] Pagination funktioniert

**Integration:**
- [ ] Frontend → Backend Kommunikation
- [ ] Authentication Flow
- [ ] Real-time Updates
- [ ] Error Handling

---

## 🐛 Falls Probleme auftreten:

### Backend startet nicht:
```bash
# Logs checken
docker-compose logs

# Services neu starten
docker-compose down
docker-compose up -d

# Database neu initialisieren
make db-init
```

### Frontend startet nicht:
```bash
cd frontend

# Node modules neu installieren
rm -rf node_modules package-lock.json
npm install

# Dev Server starten
npm run dev
```

### API Connection Error:
- Prüfe `.env` Datei im Frontend: `VITE_API_URL=http://localhost:8000/api/v1`
- Prüfe ob Backend läuft: `curl http://localhost:8000/health`

### CORS Errors:
- Backend sollte CORS bereits konfiguriert haben
- Falls nicht, in `app/main.py` CORS Middleware prüfen

---

## 🎯 Nächste Schritte (nach Testing):

1. **Feinschliff UI** - Basierend auf deinem Feedback
2. **Mehr Features** - z.B. Webhook Management UI, Deduplication UI
3. **Production Deployment** - Optional
4. **Documentation** - User Guide

---

**Letzte Aktualisierung:** 2025-10-20 21:57 Uhr
**Status:** ✅ Alle High Priority Features fertig!
**Nächster Schritt:** Testing morgen am Arbeits-PC
