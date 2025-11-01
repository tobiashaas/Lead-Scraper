# 🚀 Lead-Scraper

[![Tests](https://github.com/tobiashaas/Lead-Scraper/actions/workflows/tests.yml/badge.svg)](https://github.com/tobiashaas/Lead-Scraper/actions/workflows/tests.yml)
[![Code Quality](https://github.com/tobiashaas/Lead-Scraper/actions/workflows/code-quality.yml/badge.svg)](https://github.com/tobiashaas/Lead-Scraper/actions/workflows/code-quality.yml)
[![Security](https://github.com/tobiashaas/Lead-Scraper/actions/workflows/security.yml/badge.svg)](https://github.com/tobiashaas/Lead-Scraper/actions/workflows/security.yml)
[![CI/CD](https://github.com/tobiashaas/Lead-Scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/tobiashaas/Lead-Scraper/actions/workflows/ci.yml)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.118.0-009688.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests: 99 Passing](https://img.shields.io/badge/tests-99%20passing-brightgreen.svg)](https://github.com/tobiashaas/Lead-Scraper/actions/workflows/tests.yml)
[![Code Coverage](https://img.shields.io/badge/coverage-80%25+-brightgreen.svg)](https://github.com/tobiashaas/Lead-Scraper/actions/workflows/tests.yml)

Automatisiertes Lead-Scraping-System zur Extraktion von Unternehmensdaten aus Baden-Württemberg für IT/Bürotechnik/Dokumentenmanagement-Leads.

> 🎉 **Production Ready!** Alle Tests passing, Code Quality checks bestanden, Security Scan clean, Docker Build erfolgreich!

## 📋 Übersicht

Lead-Scraper ist ein Python-basiertes Web-Scraping-Tool, das öffentliche Branchenbücher (11880, Gelbe Seiten, etc.) durchsucht und qualitativ hochwertige B2B-Leads für die Region Baden-Württemberg sammelt.

### ✨ Features

- 🔍 **Multi-Source Scraping**: Unterstützung für mehrere Branchenbücher
- 🛡️ **Anti-Detection**: Tor Network Integration + Playwright Stealth Mode
- 🤖 **AI-Powered**: Trafilatura + Ollama für intelligente Datenextraktion (lokal!)
- 🤖 **Smart Scraper**: AI-powered fallback with automatic website enrichment (Crawl4AI + Ollama)
- 👥 **Employee Extraction**: Automatische Extraktion von Mitarbeiterdaten
- 📊 **Data Quality**: Automatische Validierung, Deduplizierung & Normalisierung
- 📈 **Monitoring & Observability**: Prometheus + Grafana Dashboards inklusive Alerts-Vorbereitung
- 🔄 **Duplicate Detection**: Fuzzy matching with auto-merge and manual review workflows
- 🗄️ **Database**: PostgreSQL mit SQLAlchemy Models
- 💾 **Automated Backups**: Geplante PostgreSQL-Backups mit Verifikation & Cloud-Sync
- 🔄 **Rate Limiting**: Intelligentes Request-Management mit Redis
- 🔐 **Authentication**: JWT-basierte API-Authentifizierung
- 📝 **Structured Logging**: JSON-basiertes Logging mit Correlation IDs
- 🐛 **Error Tracking**: Sentry Integration für Monitoring
- 🔄 **CI/CD Pipeline**: GitHub Actions für Tests, Code Quality & Security
- 🐳 **Docker Ready**: Einfaches Setup mit Docker Compose
- 📈 **REST API**: FastAPI für einfachen Datenzugriff

## 🏗️ Architektur

```text
Lead-Scraper/
├── app/
│   ├── scrapers/          # Scraper-Implementierungen
│   ├── database/          # SQLAlchemy Models & Migrations
│   ├── api/               # FastAPI Endpoints
│   ├── utils/             # Proxy Manager, Rate Limiter, Smart Scraper
│   ├── processors/        # Data Cleaning & Validation
│   ├── workers/           # RQ Workers (Scraping Jobs)
│   ├── ai/                # NER & Scoring (später)
│   └── core/              # Configuration Management
├── tests/                 # Unit & Integration Tests
├── docs/                  # Dokumentation
├── data/                  # Exports & Temp Files
├── logs/                  # Log Files
└── config/                # Config Files
```

## 🚀 Quick Start

### Voraussetzungen

- **Python 3.11+**
- **Docker & Docker Compose**
- **Tor** (für Anonymität)
- **Git**

### Installation

1. **Repository klonen**

```bash
git clone https://github.com/tobiashaas/Lead-Scraper.git
cd Lead-Scraper
```

1. **Virtual Environment erstellen**

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate    # Windows
```

1. **Dependencies installieren**

```bash
pip install -r requirements.txt
playwright install chromium
```

1. **Tor installieren & starten**

```bash
# macOS
brew install tor
tor

# Linux
sudo apt install tor
sudo systemctl start tor
```

1. **Environment Variables konfigurieren**

```bash
cp .env.example .env
# .env bearbeiten und Passwörter anpassen
```

1. **Docker Services starten**

   ```bash
   docker-compose up -d
   ```

1. **Monitoring-Stack starten (optional, empfohlen)**

   ```bash
   make monitoring-up
   # Grafana: http://localhost:3000 (admin / admin)
   # Prometheus: http://localhost:9090
   ```

1. **Worker starten (neues Terminal)**

   ```bash
   make worker
   ```

1. **Ollama Models installieren**

   ```bash
   chmod +x scripts/setup_ollama.sh
   ./scripts/setup_ollama.sh
   ```

1. **Datenbank initialisieren**

   ```bash
   python scripts/init_db.py
   ```

## 🔧 Konfiguration

### Tor Setup (Optional aber empfohlen)

Für IP-Rotation Tor Control Port aktivieren:

```bash
# /etc/tor/torrc oder /usr/local/etc/tor/torrc bearbeiten:
ControlPort 9051
HashedControlPassword <generiertes_passwort>

# Passwort generieren:
tor --hash-password "your_password"
```

### Environment Variables

Wichtigste Einstellungen in `.env`:

```bash
# Tor aktivieren/deaktivieren
TOR_ENABLED=True

# Scraping Delays (in Sekunden)
SCRAPING_DELAY_MIN=3
SCRAPING_DELAY_MAX=8

# Rate Limiting
RATE_LIMIT_REQUESTS=10
RATE_LIMIT_WINDOW=60
```

## 🔄 Job Queue & Workers

### Überblick

Scraping-Jobs werden asynchron über **RQ (Redis Queue)** abgearbeitet:

- Die API legt Jobs in Redis ab
- Worker-Prozesse ziehen Jobs von der Queue und führen sie aus
- Fortschritt und Status werden in der Datenbank aktualisiert
- Fehler führen zu automatischen Retries (konfigurierbar)

### Worker lokal starten

```bash
# Virtuelle Umgebung aktivieren und Worker starten
make worker

# Alternativ direkt
./scripts/start_worker.sh

# Windows PowerShell
./scripts/start_worker.ps1
```

## 💾 Backups & Restore

### Automatisierte Backups

- RQ Scheduler registriert tägliche, wöchentliche und monatliche Backups.
- Retention Policy sorgt für automatische Aufräumläufe (daily ×7, weekly ×4, monthly ×12).
- Optionale Features: Gzip-Kompression, GPG-Verschlüsselung, Cloud Sync (S3/GCS/Azure), Integritätsprüfung.
- Konfiguration via `.env` (siehe `.env.example`) oder Secrets Manager.

### Manuelle Befehle

```bash
# Backup anstoßen (komprimiert + Verifikation)
make backup-db

# Tägliches Backup mit Cleanup
make backup-daily

# Wöchentliches Backup mit Verschlüsselung
make backup-weekly

# Backups auflisten
make backup-list

# Letztes Backup verifizieren
make backup-verify

# Interaktives Restore
make restore-db

# Test-Restore ohne produktive DB zu überschreiben
make restore-test
```

### Weitere Infos

- Ausführliche Anleitung: [`docs/BACKUP.md`](docs/BACKUP.md)
- Produktionsleitfaden inkl. Connection Pooling: [`docs/PRODUCTION.md`](docs/PRODUCTION.md)

### Docker-Worker

```bash
# Entwicklung (docker-compose)
make worker-dev

# Produktion (docker-compose.prod.yml)
make worker-prod

# Logs verfolgen
make worker-logs
```

## 🤖 Smart Scraper & AI Enrichment

### Overview

Smart Scraper provides intelligent fallback and enrichment for scraping jobs using AI-powered website analysis.

**Capabilities:**

- Automatic fallback when standard scrapers fail
- Enriches results with data from company websites
- Extracts directors, services, team size, technologies
- Uses local Ollama (no cloud APIs, GDPR-compliant)

### Quick Start

**Enable for a Job:**

```bash
curl -X POST http://localhost:8000/api/v1/scraping/jobs \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "source_name": "11880",
    "city": "Stuttgart",
    "industry": "IT-Service",
    "enable_smart_scraper": true,
    "smart_scraper_mode": "enrichment",
    "max_pages": 3
  }'
```

**Enable Globally:**

```bash
# In .env
SMART_SCRAPER_ENABLED=True
SMART_SCRAPER_MODE=enrichment
SMART_SCRAPER_MAX_SITES=10
```

### Modes

- **Enrichment**: Always enrich results with website data (best quality)
- **Fallback**: Only use smart scraper if standard scraper fails (best performance)
- **Disabled**: Skip smart scraper entirely (fastest)

### Dokumentation

- [AI Scraping Guide](docs/AI-SCRAPING.md): Comprehensive guide
- [Smart Scraper Integration](docs/AI-SCRAPING.md#smart-scraper-integration): Integration details
- [Configuration](docs/AI-SCRAPING.md#configuration): Configuration options
- [Monitoring Guide](docs/MONITORING.md): Prometheus/Grafana Setup & Dashboards

### Model Selection

Wähle das passende Ollama-Modell abhängig von Durchsatz und Genauigkeit:

- **llama3.2** – Höchste Feldgenauigkeit, robust für Produktionsjobs.
- **llama3.2:1b** – Schnell und ressourcensparend, ideal für Bulk-Läufe.
- **mistral** – Ausgewogene Performance, gute Allround-Wahl.
- **qwen2.5** – Stark bei Kontaktdaten & mehrsprachigen Seiten.

Aktiviere die automatische Auswahl via `.env`:

```bash
OLLAMA_MODEL_SELECTION_ENABLED=true
OLLAMA_MODEL_PRIORITY=llama3.2,llama3.2:1b,mistral,qwen2.5
```

Benchmark- und Optimierungsbefehle:

- `make benchmark-models` – Modelle gegen Testcases messen
- `make benchmark-report` – Markdown-Bericht ausgeben
- `make benchmark-prompts` – Prompt-Optimierung durchführen

Details & Ergebnisse: [docs/AI-SCRAPING.md#model-benchmarks-performance](docs/AI-SCRAPING.md#model-benchmarks-performance)

### Queue-Statistiken & Monitoring

```bash
# Queue-Statistiken ausgeben
make worker-stats

# API Endpoint
curl http://localhost:8000/api/v1/scraping/jobs/stats
```

### Skalierung

- Mehrere Worker-Instanzen können parallel laufen
- Docker Compose: `docker-compose up --scale worker=4`
- Produktions-Setup: zusätzliche `worker-N` Services ergänzen
- Nur ein Worker sollte `--with-scheduler` nutzen, um doppelte geplante Jobs zu vermeiden

## 📖 Verwendung

### API starten (später)

```bash
uvicorn app.main:app --reload
```

API verfügbar unter: `http://localhost:8000`
Docs verfügbar unter: `http://localhost:8000/docs`

### Scraping Job starten

```bash
# 11880 Scraper testen
python scrape_11880_test.py
```

Oder programmatisch:

```python
from app.scrapers.eleven_eighty import scrape_11880

results = await scrape_11880(
    city="Stuttgart",
    industry="IT-Service",
    max_pages=2,
    use_tor=False
)
```

## 🧪 Testing

```bash
# Alle Tests ausführen
pytest

# Mit Coverage Report
pytest --cov=app --cov-report=html

# Nur Unit Tests
pytest tests/unit/

# Nur Integration Tests
pytest tests/integration/
```

## 🗺️ Roadmap

### Phase 1: MVP (4-6 Wochen) ✅ In Progress

- [x] Projektstruktur & Setup
- [x] Docker Compose Environment
- [ ] BaseScraper Framework
- [ ] 11880 Scraper
- [ ] Basis ETL Pipeline

### Phase 2: Erweiterung (4-6 Wochen)

- [ ] Gelbe Seiten Scraper
- [ ] Data Validation & Cleaning
- [ ] Deduplizierung
- [ ] FastAPI Endpoints

### Phase 3: AI & Automation (4-6 Wochen)

- [ ] Named Entity Recognition
- [ ] Lead Scoring
- [ ] Automatische Scraping-Jobs
- [ ] SmartWe Integration

### Phase 4: Production (2-4 Wochen)

- [ ] Testing & Bug Fixes
- [ ] Monitoring & Logging
- [ ] VPS Deployment
- [ ] Dokumentation

## ⚖️ Rechtliche Hinweise

### Wichtige Hinweise

Dieses Tool scraped öffentlich zugängliche Daten aus Branchenbüchern.

- ✅ **Erlaubt**: Öffentliche Branchenbücher (11880, Gelbe Seiten)
- ⚠️ **Vorsicht**: robots.txt beachten, Rate Limiting einhalten
- ❌ **Verboten**: LinkedIn/Xing Scraping (ToS-Verstoß)

**Empfehlung**:

- Langsames Scraping (3-8 Sekunden Delay)
- Tor/VPN für Anonymität
- Bei Unsicherheit rechtliche Beratung einholen

## 🤝 Contributing

Contributions sind willkommen! Bitte:

1. Fork das Repository
2. Feature Branch erstellen (`git checkout -b feature/AmazingFeature`)
3. Änderungen committen (`git commit -m 'Add AmazingFeature'`)
4. Branch pushen (`git push origin feature/AmazingFeature`)
5. Pull Request öffnen

## 📝 License

Dieses Projekt ist für interne Nutzung bei Kunze & Ritter vorgesehen.

## 📧 Kontakt

### Kunze & Ritter GmbH

- Website: [kunze-ritter.de](https://kunze-ritter.de)
- GitHub: [@Kunze-Ritter](https://github.com/Kunze-Ritter)

## 🙏 Acknowledgments

- [Playwright](https://playwright.dev/) - Browser Automation
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Web Framework
- [Tor Project](https://www.torproject.org/) - Anonymity Network
- [spaCy](https://spacy.io/) - NLP Library

---

**Status**: 🚧 In Development - Phase 1 (MVP)

**Ziel**: 10.000+ qualitativ hochwertige Leads/Monat aus Baden-Württemberg
