# 🚀 KR-Lead-Scraper

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

KR-Lead-Scraper ist ein Python-basiertes Web-Scraping-Tool, das öffentliche Branchenbücher (11880, Gelbe Seiten, etc.) durchsucht und qualitativ hochwertige B2B-Leads für die Region Baden-Württemberg sammelt.

### ✨ Features

- 🔍 **Multi-Source Scraping**: Unterstützung für mehrere Branchenbücher
- 🛡️ **Anti-Detection**: Tor Network Integration + Playwright Stealth Mode
- 🤖 **AI-Powered**: Trafilatura + Ollama für intelligente Datenextraktion (lokal!)
- 🧠 **Smart Scraper**: Hybrid-Scraper mit automatischen Fallbacks
- 👥 **Employee Extraction**: Automatische Extraktion von Mitarbeiterdaten
- 📊 **Data Quality**: Automatische Validierung, Deduplizierung & Normalisierung
- 🗄️ **Database**: PostgreSQL mit SQLAlchemy Models
- 🔄 **Rate Limiting**: Intelligentes Request-Management mit Redis
- 🔐 **Authentication**: JWT-basierte API-Authentifizierung
- 📝 **Structured Logging**: JSON-basiertes Logging mit Correlation IDs
- 🐛 **Error Tracking**: Sentry Integration für Monitoring
- 🔄 **CI/CD Pipeline**: GitHub Actions für Tests, Code Quality & Security
- 🐳 **Docker Ready**: Einfaches Setup mit Docker Compose
- 📈 **REST API**: FastAPI für einfachen Datenzugriff

## 🏗️ Architektur

```
KR-Lead-Scraper/
├── app/
│   ├── scrapers/          # Scraper-Implementierungen
│   ├── database/          # SQLAlchemy Models & Migrations
│   ├── api/               # FastAPI Endpoints
│   ├── utils/             # Proxy Manager, Rate Limiter, etc.
│   ├── processors/        # Data Cleaning & Validation
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
   git clone https://github.com/tobiashaas/KR-Lead-Scraper.git
   cd KR-Lead-Scraper
   ```

2. **Virtual Environment erstellen**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # venv\Scripts\activate    # Windows
   ```

3. **Dependencies installieren**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Tor installieren & starten**
   ```bash
   # macOS
   brew install tor
   tor

   # Linux
   sudo apt install tor
   sudo systemctl start tor
   ```

5. **Environment Variables konfigurieren**
   ```bash
   cp .env.example .env
   # .env bearbeiten und Passwörter anpassen
   ```

6. **Docker Services starten**
   ```bash
   docker-compose up -d
   ```

7. **Ollama Models installieren**
   ```bash
   chmod +x scripts/setup_ollama.sh
   ./scripts/setup_ollama.sh
   ```

8. **Datenbank initialisieren**
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

## 📊 Technologie-Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy
- **Database**: PostgreSQL 15
- **Cache**: Redis 7
- **Scraping**: Playwright, BeautifulSoup4, httpx, Trafilatura
- **AI Scraping**: Crawl4AI, Ollama (llama3.2, mistral, qwen2.5)
- **Anonymität**: Tor Network (stem, pysocks)
- **Data Processing**: fuzzywuzzy, email-validator, phonenumbers
- **Testing**: pytest, pytest-asyncio
- **DevOps**: Docker, Docker Compose

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

**WICHTIG**: Dieses Tool scraped öffentlich zugängliche Daten aus Branchenbüchern.

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

**Kunze & Ritter GmbH**
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
