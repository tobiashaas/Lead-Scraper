# 🚀 KR-Lead-Scraper - Entwickler-Implementierungsplan
## Automatisierte Unternehmensdaten-Extraktion Baden-Württemberg

### 📋 Projekt-Übersicht
**Ziel**: Entwicklung eines automatisierten Lead-Scraping-Systems zur Extraktion von 10.000+ Unternehmensdaten/Monat aus Baden-Württemberg für IT/Bürotechnik/Dokumentenmanagement-Leads.

**Technologien**: Python 3.11+, FastAPI, PostgreSQL, Redis, Docker
**Architektur**: Monolithische Anwendung mit modularer Struktur (später ausbaubar)
**Deployment**: Lokal (starker PC), später optional VPS

---

## 🏗️ Phase 1: Foundation Setup (Woche 1-3)

### 1.1 Projekt-Initialisierung
```bash
# Repository erstellen
git clone https://github.com/Kunze-Ritter/KR-Lead-Scraper.git
cd kr-lead-scraper

# Python Virtual Environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Grundstruktur erstellen
mkdir -p {app,scrapers,database,utils,tests,docs,data}
```

### 1.2 Development Environment Setup
```bash
# Docker Compose für lokale Entwicklung (PostgreSQL + Redis)
docker-compose up -d postgres redis

# Database Setup
alembic init migrations
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

### 1.3 Core Module entwickeln
**Priorität: HOCH**
```python
# app/database/models.py - SQLAlchemy Models
# app/core/config.py - Configuration Management (Pydantic Settings)
# app/scrapers/base.py - Base Scraper Class
# app/utils/proxy_manager.py - Proxy Rotation
# app/utils/rate_limiter.py - Rate Limiting mit Redis
```

---

## 🔧 Phase 2: Scraper Service (Woche 4-8)

### 2.1 Base Scraper Framework
**Aufgaben**:
- [ ] BaseScraper Abstract Class implementieren
- [ ] Rate Limiting mit Redis Backend
- [ ] Data Extraction Framework mit BeautifulSoup/Playwright
- [ ] Error Handling & Retry Logic

**Proxy & Anonymität Setup**:

```python
# app/utils/proxy_manager.py
# START: Tor Network (kostenlos, später erweiterbar)

import httpx
from stem import Signal
from stem.control import Controller

class TorProxyManager:
    """Tor Network für Anonymität - kostenlos und ausreichend für Start"""

    def __init__(self):
        self.tor_proxy = "socks5://127.0.0.1:9050"
        self.control_port = 9051
        self.password = "your_tor_password"

    async def get_new_identity(self):
        """Neue Tor-Identität anfordern (neue IP)"""
        with Controller.from_port(port=self.control_port) as controller:
            controller.authenticate(password=self.password)
            controller.signal(Signal.NEWNYM)

    def get_proxy_config(self):
        return {"http://": self.tor_proxy, "https://": self.tor_proxy}

# Später erweiterbar auf:
# - Residential Proxies (Bright Data, Smartproxy)
# - Proxy-Rotation mit Liste
# - Smart Proxy Selection basierend auf Erfolgsrate
```

**Tor Installation**:

```bash
# macOS
brew install tor
tor  # Startet Tor Service auf Port 9050

# Linux
sudo apt install tor
sudo systemctl start tor

# Tor Control Port aktivieren (für IP-Rotation)
# In /etc/tor/torrc oder /usr/local/etc/tor/torrc:
# ControlPort 9051
# HashedControlPassword <generiertes_passwort>
```

### 2.2 Konkrete Scraper implementieren

#### 2.2.1 11880 Scraper (START HIER - NIEDRIGSTE KOMPLEXITÄT)

```python
# app/scrapers/eleven_eighty.py
class ElevenEightyScaper(BaseScraper):
    """
    Öffentliches Branchenbuch, relativ scraping-freundlich
    Keine Login erforderlich, einfache HTML-Struktur
    """

    async def get_search_urls(self, **filters):
        # BW-spezifische Suchterms
        cities = ['Stuttgart', 'Karlsruhe', 'Mannheim', 'Freiburg', 'Heidelberg', ...]
        industries = ['IT-Service', 'Bürotechnik', 'Dokumentenmanagement', ...]

    async def parse_search_results(self, html, url):
        # BeautifulSoup Implementation
```

#### 2.2.2 Gelbe Seiten Scraper
- Ähnliche Struktur wie 11880
- Verschiedene DOM-Selektoren
- Auch öffentlich zugänglich

#### 2.2.3 LinkedIn/Xing Scraper (OPTIONAL - HOHES RISIKO!)
**⚠️ WARNUNG**: LinkedIn und Xing verbieten Scraping explizit in ihren ToS!
- **Rechtliches Risiko**: Account-Sperrung, Abmahnungen möglich
- **Technisch komplex**: CAPTCHA, Session-Management, JavaScript-Rendering
- **Empfehlung**: Nur mit Anwalt absprechen oder offizielle APIs nutzen
- **Alternative**: LinkedIn Sales Navigator API (kostenpflichtig, aber legal)

### 2.3 Data Processing Pipeline

```python
# app/processors/
- data_cleaner.py       # Normalisierung, Bereinigung
- deduplicator.py      # Fuzzy Matching für Duplikate (fuzzywuzzy)
- validator.py         # Email/Phone/URL Validation
- enricher.py          # Daten-Anreicherung
```

### 2.4 Playwright Setup (Empfohlen für moderne Websites)

**Warum Playwright?**
- Unterstützt JavaScript-Rendering (wichtig für moderne Sites)
- Stealth-Mode gegen Bot-Detection
- Einfach erweiterbar auf andere Browser-Engines
- Gute Performance

```python
# app/utils/browser_manager.py
from playwright.async_api import async_playwright
import random

class PlaywrightBrowserManager:
    """Playwright mit Stealth-Mode und Tor-Integration"""

    def __init__(self, use_tor=True):
        self.use_tor = use_tor
        self.tor_proxy = "socks5://127.0.0.1:9050" if use_tor else None

    async def create_browser_context(self):
        """Browser-Context mit Anti-Detection Settings"""
        playwright = await async_playwright().start()

        # Verschiedene User-Agents für Rotation
        user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        ]

        browser = await playwright.chromium.launch(
            headless=True,
            proxy={"server": self.tor_proxy} if self.use_tor else None
        )

        context = await browser.new_context(
            user_agent=random.choice(user_agents),
            viewport={"width": 1920, "height": 1080},
            locale="de-DE",
            timezone_id="Europe/Berlin",
            # Anti-Detection: Verhindert WebDriver-Erkennung
            java_script_enabled=True,
            bypass_csp=True
        )

        # Stealth-Mode: WebDriver-Property verstecken
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        return context, browser, playwright

    async def close(self, browser, playwright):
        await browser.close()
        await playwright.stop()

# Verwendung im Scraper:
# browser_manager = PlaywrightBrowserManager(use_tor=True)
# context, browser, pw = await browser_manager.create_browser_context()
# page = await context.new_page()
# await page.goto("https://www.11880.com/...")
```

**Installation**:

```bash
pip install playwright playwright-stealth
playwright install chromium  # Lädt Chromium-Browser herunter
```

**Wann Playwright vs. BeautifulSoup?**
- **BeautifulSoup**: Einfache statische HTML-Seiten (schneller, weniger Ressourcen)
- **Playwright**: JavaScript-heavy Websites, Login-Flows, dynamische Inhalte

### 2.5 CAPTCHA Handling

**Strategie für Start**:

1. **Vermeidung (BESTE Option für Anfang)**:
   - Langsames Scraping (1 Request / 5-10 Sekunden)
   - Playwright Stealth Mode
   - Tor IP-Rotation alle 50-100 Requests
   - Human-like Behavior (zufällige Delays, Mouse-Bewegungen)

2. **Falls CAPTCHAs auftreten**:
   - **2Captcha** (~$3 pro 1000 CAPTCHAs) - einfache Integration
   - **CapSolver** (~$2 pro 1000) - günstiger
   - **Anti-Captcha** (~$2 pro 1000) - gute API

```python
# app/utils/captcha_solver.py (optional, nur bei Bedarf)
import httpx

class TwoCaptchaSolver:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "http://2captcha.com"

    async def solve_recaptcha(self, site_key: str, page_url: str):
        """reCAPTCHA v2 lösen"""
        # Implementation nur bei Bedarf
        pass
```

---

## 🤖 Phase 3: AI Integration (Woche 9-12)

### 3.1 Named Entity Recognition (NER)

```python
# app/ai/ner_processor.py
import spacy

class GermanNERProcessor:
    def __init__(self):
        self.nlp = spacy.load("de_core_news_lg")

    def extract_entities(self, text: str) -> Dict:
        doc = self.nlp(text)
        entities = {
            "persons": [ent.text for ent in doc.ents if ent.label_ == "PER"],
            "organizations": [ent.text for ent in doc.ents if ent.label_ == "ORG"],
            "locations": [ent.text for ent in doc.ents if ent.label_ == "LOC"]
        }
        return entities
```

### 3.2 Decision Maker Scoring

```python
# app/ai/scorer.py
class DecisionMakerScorer:
    """Bewertet Entscheidungsgewalt basierend auf Job Title"""

    DECISION_MAKER_KEYWORDS = {
        "c_level": ["CEO", "CTO", "CIO", "Geschäftsführer", "Vorstand"],
        "director": ["Direktor", "Leiter", "Head of", "Director"],
        "manager": ["Manager", "Teamleiter", "Abteilungsleiter"]
    }

    def score_contact(self, job_title: str) -> float:
        # Scoring: C-Level=1.0, Director=0.7, Manager=0.5
        pass
```

---

## 📊 Phase 4: Database & ETL (Woche 13-16)

### 4.1 PostgreSQL Schema Implementation
- Alle Tabellen aus database_schema_complete.sql implementieren
- Indizes für Performance-Optimierung
- Partitionierung für große Datenmengen

### 4.2 ETL Pipeline

```python
# app/etl/pipeline.py
class ETLPipeline:
    async def process_raw_data(self, raw_data: Dict) -> ProcessedData:
        """
        1. Validierung (Email, Telefon, Website)
        2. Normalisierung (Adressen, Namen)
        3. Anreicherung mit AI (NER, Scoring)
        4. Deduplizierung (Fuzzy Matching)
        5. Database Storage
        """
```

---

## 🔗 Phase 5: API Gateway & Integration (Woche 17-20)

### 5.1 FastAPI Application

```python
# app/main.py
from fastapi import FastAPI, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="KR Lead Scraper API",
    description="Automated Company Data Extraction - Baden-Württemberg",
    version="1.0.0"
)

@app.post("/scraping/start")
async def start_scraping_job(
    job_config: ScrapingJobConfig,
    background_tasks: BackgroundTasks
):
    """Neuen Scraping-Job im Hintergrund starten"""
    background_tasks.add_task(run_scraping_job, job_config)
    return {"status": "started", "job_id": job_config.id}

@app.get("/companies")
async def get_companies(filters: CompanyFilters = Depends()):
    """Gefilterte Unternehmensliste abrufen"""

@app.get("/leads")
async def get_leads(filters: LeadFilters = Depends()):
    """Lead-Management Endpoints"""

@app.get("/stats")
async def get_statistics():
    """Scraping-Statistiken und Performance-Metriken"""
```

### 5.2 SmartWe Integration

```python
# app/integrations/smartwe_client.py
class SmartWeClient:
    async def sync_companies(self, companies: List[Company]):
        """Unternehmen zu SmartWe synchronisieren"""

    async def sync_contacts(self, contacts: List[Contact]):
        """Kontakte zu SmartWe synchronisieren"""
```

---

## 🧪 Phase 6: Testing & Quality Assurance

### 6.1 Test Setup

```python
# tests/conftest.py
import pytest
from factory import Factory, Faker
from app.database.models import Company, Contact

class CompanyFactory(Factory):
    class Meta:
        model = Company

    name = Faker('company')
    website = Faker('url')
    city = Faker('city')
```

### 6.2 Test Kategorien

- **Unit Tests**: Einzelne Module (>70% Coverage ausreichend)
- **Integration Tests**: Database, API Endpoints
- **E2E Tests**: Kompletter Scraping-Workflow
- **Smoke Tests**: Schnelle Checks nach Deployment

---

## 🚀 Phase 7: Deployment & Monitoring

### 7.1 Lokales Deployment mit Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/kr_leads
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis
    volumes:
      - ./data:/app/data  # Für Logs und Exports
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: kr_leads
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### 7.2 VPS Deployment (Optional)

**Empfohlene VPS-Provider**:

1. **Hetzner Cloud** (~€20/Monat für CPX31: 4 vCPU, 8GB RAM)
2. **Contabo** (~€15/Monat, mehr RAM aber langsamere CPUs)
3. **DigitalOcean** (~$24/Monat, gute Performance)

**Setup-Schritte**:

```bash
# Auf VPS
git clone https://github.com/Kunze-Ritter/KR-Lead-Scraper.git
cd KR-Lead-Scraper
docker-compose up -d

# Nginx Reverse Proxy für HTTPS
sudo apt install nginx certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 7.3 Monitoring & Logging

**Einfaches Setup**:

```python
# app/utils/logger.py
import logging
from logging.handlers import RotatingFileHandler

# File Logging mit Rotation
handler = RotatingFileHandler(
    'logs/scraper.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)

# Optional: Telegram Notifications für Fehler
async def send_telegram_alert(message: str):
    """Kritische Fehler per Telegram melden"""
    pass
```

**Monitoring-Optionen**:

1. **Einfach**: Log-Files + Cron-Job für Checks
2. **Mittel**: Grafana + Prometheus (via Docker)
3. **Fortgeschritten**: Sentry für Error Tracking (~$26/Monat)

---

## 📅 Entwicklungs-Roadmap (Flexibel)

### Phase 1: MVP - Basis-Scraper (4-6 Wochen)

- [ ] Repository Setup & Projektstruktur
- [ ] Docker Compose Environment (PostgreSQL + Redis)
- [ ] Database Schema erstellen
- [ ] BaseScraper Framework
- [ ] 11880 Scraper implementieren
- [ ] Basis ETL Pipeline
- **Deliverable**: 100+ BW-Unternehmen erfolgreich gescraped & in DB gespeichert

### Phase 2: Erweiterung & Qualität (4-6 Wochen)

- [ ] Gelbe Seiten Scraper
- [ ] Data Validation & Cleaning
- [ ] Deduplizierung
- [ ] Anti-Detection (User-Agent Rotation, Rate Limiting)
- [ ] Basic FastAPI Endpoints
- **Deliverable**: 1.000+ qualitativ hochwertige Leads

### Phase 3: AI & Automation (4-6 Wochen)

- [ ] NER für deutsche Texte (spaCy)
- [ ] Decision Maker Scoring
- [ ] Lead Scoring Algorithm
- [ ] Automatische Scraping-Jobs (Scheduler)
- [ ] SmartWe Integration
- **Deliverable**: Automatisierte Pipeline mit AI-Anreicherung

### Phase 4: Production & Skalierung (2-4 Wochen)

- [ ] Testing & Bug Fixes
- [ ] Monitoring & Logging
- [ ] VPS Deployment (optional)
- [ ] Performance-Optimierung
- [ ] Dokumentation
- **Deliverable**: Production-ready System

---

## 🎯 Erfolgskriterien

### Technische KPIs

- [ ] **10.000+ Leads/Monat** aus BW-Quellen
- [ ] **80%+ Datenqualität** (realistische Ziel für Start)
- [ ] **<3 Sekunden** API Response Zeit
- [ ] **<10% Fehlerrate** bei Scraping-Operationen
- [ ] **Automatische Fehler-Recovery**

### Business KPIs

- [ ] **SmartWe Integration** funktional
- [ ] **Lead-Scoring** Genauigkeit >75%
- [ ] **Deduplizierung** funktioniert zuverlässig
- [ ] **Export-Funktionen** (CSV, Excel) vorhanden

---

## 🚨 Kritische Risiken & Mitigation

### 1. Website-Blocking & Anti-Bot-Maßnahmen

**Risiko**: Scraper werden erkannt und blockiert

**Mitigation**:

- **Rate Limiting**: Max. 1 Request pro 3-5 Sekunden pro Domain
- **User-Agent Rotation**: Verschiedene Browser simulieren
- **Request Delays**: Zufällige Wartezeiten (2-10 Sekunden)
- **Proxies**: Bei Bedarf Residential Proxies nutzen
- **Fallback**: Manuelle Checks bei wiederholten Fehlern

### 2. Rechtliche Risiken (DSGVO, Web Scraping)

**Risiko**: Abmahnungen, rechtliche Probleme

**Mitigation**:

- **Fokus auf öffentliche Daten**: Branchenbücher sind relativ sicher
- **Keine personenbezogenen Daten ohne Rechtsgrundlage**: Vorsicht bei LinkedIn/Xing
- **Opt-Out Mechanismus**: Unternehmen können Löschung beantragen
- **Rechtliche Beratung**: Bei Unsicherheit Anwalt konsultieren
- **VPN/Proxies**: Zusätzlicher Schutz der Identität

### 3. Performance & Skalierung

**Risiko**: System ist zu langsam für 10k+ Leads/Monat

**Mitigation**:

- **Async/Await**: Nicht-blockierende I/O-Operationen
- **Connection Pooling**: Wiederverwendung von DB-Connections
- **Redis Caching**: Häufig abgerufene Daten cachen
- **Batch Processing**: Mehrere Requests parallel (mit Limit)
- **Monitoring**: Engpässe frühzeitig erkennen

### 4. Datenqualität

**Risiko**: Schlechte/veraltete Daten

**Mitigation**:

- **Email-Validation**: Syntax-Check + optional SMTP-Verify
- **Deduplizierung**: Fuzzy Matching für ähnliche Einträge
- **Manuelle Stichproben**: Regelmäßige Qualitätschecks
- **Update-Mechanismus**: Alte Daten regelmäßig neu scrapen

---

## 📚 Konkrete Nächste Schritte

### Woche 1: Setup & Grundlagen

1. **Repository & Projektstruktur erstellen**
   ```bash
   mkdir -p app/{scrapers,database,api,utils,ai,processors,integrations}
   mkdir -p {tests,docs,data,logs}
   ```

2. **Docker Compose aufsetzen**
   - PostgreSQL Container
   - Redis Container
   - Basis-App Container

3. **Dependencies installieren**

   ```bash
   # Core Framework
   pip install fastapi uvicorn sqlalchemy alembic psycopg2-binary

   # Scraping & Browser
   pip install playwright beautifulsoup4 httpx lxml
   pip install playwright-stealth  # Anti-Detection
   playwright install chromium

   # Tor Integration
   pip install stem  # Tor Controller für IP-Rotation
   pip install pysocks  # SOCKS Proxy Support

   # Data Processing
   pip install redis fuzzywuzzy python-Levenshtein
   pip install email-validator phonenumbers

   # AI/NLP (optional, später)
   # pip install spacy
   # python -m spacy download de_core_news_lg

   # Config & Utils
   pip install python-dotenv pydantic-settings
   ```

   **Tor installieren**:

   ```bash
   # macOS
   brew install tor

   # Linux
   sudo apt install tor
   ```

4. **Database Schema erstellen** (Alembic Migrations)

### Woche 2-3: Erster funktionierender Scraper

1. **BaseScraper Class** implementieren
   - Abstract Base Class mit gemeinsamer Logik
   - Rate Limiting
   - Error Handling
   - Retry Logic

2. **11880 Scraper** als Proof of Concept
   - Einfache Suche nach "IT Service Stuttgart"
   - HTML Parsing mit BeautifulSoup
   - Daten in PostgreSQL speichern

3. **Erste Tests** schreiben
   - Unit Tests für Parser
   - Integration Test für kompletten Workflow

### Woche 4+: Iterative Erweiterung

1. **Weitere Scraper** hinzufügen (Gelbe Seiten, etc.)
2. **Data Processing** verbessern (Validation, Cleaning)
3. **FastAPI Endpoints** für Zugriff auf Daten
4. **Monitoring & Logging** implementieren

---

## 💰 Geschätzte Kosten (Monatlich)

### Minimal-Setup (Lokal)

- **Hardware**: Vorhandener PC (€0)
- **Software**: Open Source (€0)
- **Optional - CAPTCHA Service**: €0-20 (bei Bedarf)
- **Optional - Proxies**: €0-50 (bei Bedarf)
- **Gesamt**: **€0-70/Monat**

### Mit VPS

- **VPS**: €15-25 (Hetzner/Contabo)
- **Domain**: €1-2
- **CAPTCHA Service**: €10-30
- **Proxies**: €50-100 (bei intensiver Nutzung)
- **Gesamt**: **€76-157/Monat**

---

## 🎓 Empfohlene Lernressourcen

### Web Scraping

- **Playwright Docs**: https://playwright.dev/python/
- **BeautifulSoup Tutorial**: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- **Anti-Detection**: Recherche zu "web scraping best practices"

### FastAPI & Python

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **SQLAlchemy Tutorial**: https://docs.sqlalchemy.org/
- **Async Python**: asyncio Dokumentation

### Rechtliches

- **DSGVO Basics**: Bundesdatenschutzbeauftragter Website
- **Web Scraping Legal**: Recherche zu aktuellen Urteilen (z.B. HiQ vs LinkedIn)

---

## ✅ Zusammenfassung der Änderungen

**Entfernt**:
- ❌ Kubernetes/K8s Deployment
- ❌ RabbitMQ (Message Queue nicht nötig für Monolith)
- ❌ Microservices-Architektur
- ❌ Komplexe Service-zu-Service Kommunikation
- ❌ Prometheus/Grafana (optional, nicht Pflicht)

**Hinzugefügt**:
- ✅ Docker Compose für lokales Setup
- ✅ VPS Deployment-Optionen (Hetzner, Contabo, DigitalOcean)
- ✅ Konkrete Proxy-Empfehlungen mit Preisen
- ✅ CAPTCHA-Service Optionen
- ✅ Rechtliche Hinweise & Risiken
- ✅ Realistische Kostenübersicht
- ✅ Monolithische Architektur (einfacher zu starten)

**Fokus**:
- 🎯 Pragmatischer Start mit minimalem Setup
- 🎯 Lokale Entwicklung auf starkem PC
- 🎯 Später optional auf VPS skalierbar
- 🎯 Öffentliche Branchenbücher als Hauptquelle (geringeres Risiko)
