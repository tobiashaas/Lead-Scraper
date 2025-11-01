# 🤖 AI-Powered Web Scraping

Intelligente Datenextraktion von Websites mit Trafilatura + Ollama.

## 📋 Übersicht

Der AI Web Scraper nutzt Large Language Models (LLMs) um strukturierte Daten aus Websites zu extrahieren - ohne CSS-Selektoren oder XPath!

### ✨ Features

- 🧠 **KI-basierte Extraktion**: Nutzt Ollama (lokal!) für intelligente Datenextraktion
- 👥 **Mitarbeiter-Daten**: Extrahiert Namen, Positionen, Kontaktdaten
- 📞 **Kontaktinformationen**: Email, Telefon, Adresse, Social Media
- 🛠️ **Services/Produkte**: Automatische Erkennung von Angeboten
- 🎯 **Custom Prompts**: Extrahiere beliebige Daten mit eigenen Prompts
- 💯 **Strukturierte Ausgabe**: JSON-Format, direkt verwendbar

## 🚀 Quick Start

### 1. Ollama installieren & starten

```bash
# Ollama installieren (falls noch nicht geschehen)
# https://ollama.ai

# Ollama starten
ollama serve

# Llama 3.2 Model herunterladen
ollama pull llama3.2
```

### 2. AI Scraper nutzen

```python
from app.utils.ai_web_scraper import AIWebScraper

# Scraper initialisieren
scraper = AIWebScraper()

# Komplette Firmendaten extrahieren
data = scraper.extract_company_data("https://company.com")

print(data)
# {
#     "company_name": "Example GmbH",
#     "employees": [
#         {"name": "Max Mustermann", "position": "CEO", "email": "max@company.com"}
#     ],
#     "contact": {
#         "email": "info@company.com",
#         "phone": "+49 123 456789",
#         "address": "Musterstraße 1, 70173 Stuttgart"
#     },
#     "services": ["IT-Beratung", "Cloud-Services", "Softwareentwicklung"],
#     "about": "Führender IT-Dienstleister in Baden-Württemberg..."
# }
```

## 🔄 Smart Scraper Integration

### Overview

The Smart Scraper is integrated into the main scraping pipeline and provides intelligent fallback and enrichment capabilities.

**Features:**
- 🔄 **Automatic Fallback**: Uses AI scraper when standard scrapers fail
- 📈 **Data Enrichment**: Enriches standard scraper results with website data
- 🎯 **Multiple Methods**: 4 fallback methods (Crawl4AI+Ollama → Trafilatura+Ollama → Playwright+BS4 → httpx+BS4)
- ⚙️ **Configurable**: Enable/disable per job or globally
- 📊 **Progress Tracking**: Real-time progress updates during enrichment

### Operational Modes

**1. Enrichment Mode (Default)**
- Always enriches standard scraper results with website data
- Scrapes company websites to extract additional information
- Best for: Maximum data quality, when websites are available
- Example: Standard scraper finds company name + address, smart scraper adds directors + services from website

**2. Fallback Mode**
- Only uses smart scraper when standard scraper returns 0 results
- Attempts to scrape websites directly when directory scraping fails
- Best for: Backup strategy, when standard scrapers are unreliable
- Example: Standard scraper finds nothing, smart scraper scrapes company website directly

**3. Disabled Mode**
- Smart scraper is completely disabled
- Only standard scrapers are used
- Best for: Fast scraping, when AI enrichment is not needed

### Configuration

**Global Settings (`.env`):**
```bash
SMART_SCRAPER_ENABLED=True  # Enable globally
SMART_SCRAPER_MODE=enrichment  # Default mode
SMART_SCRAPER_MAX_SITES=10  # Max websites per job
SMART_SCRAPER_TIMEOUT=30  # Timeout per website
```

**Per-Job Configuration (API):**
```json
POST /api/v1/scraping/jobs
{
  "source_name": "11880",
  "city": "Stuttgart",
  "industry": "IT-Service",
  "enable_smart_scraper": true,
  "smart_scraper_mode": "enrichment",
  "smart_scraper_max_sites": 5,
  "use_ai": true
}
```

### Usage Examples

**Example 1: Enrichment Mode**
```python
# Standard scraper finds basic data
# Smart scraper enriches with website data

job = {
    "source_name": "11880",
    "city": "Stuttgart",
    "industry": "IT-Service",
    "enable_smart_scraper": True,
    "smart_scraper_mode": "enrichment",
    "max_pages": 3
}

# Result:
# - Company name, address, phone from 11880
# - Directors, services, team_size from website (smart scraper)
# - Sources: ["11880", "smart_scraper"]
```

**Example 2: Fallback Mode**
```python
# Use smart scraper only if standard scraper fails

job = {
    "source_name": "11880",
    "city": "Small Town",  # Might have no results
    "industry": "Niche Industry",
    "enable_smart_scraper": True,
    "smart_scraper_mode": "fallback",
    "max_pages": 5
}

# If 11880 returns 0 results:
# - Smart scraper attempts to find companies via web search
# - Scrapes company websites directly
# - Sources: ["smart_scraper"]
```

**Example 3: Selective Enrichment**
```python
# Enrich only specific results

job = {
    "source_name": "gelbe_seiten",
    "city": "Berlin",
    "industry": "Consulting",
    "enable_smart_scraper": True,
    "smart_scraper_max_sites": 3,  # Only enrich first 3
    "use_ai": True
}

# Result:
# - First 3 companies: Enriched with website data
# - Remaining companies: Standard scraper data only
```

### How It Works

**Pipeline Flow:**
```
1. Standard Scraper (11880, Gelbe Seiten, etc.)
   ↓ Returns ScraperResult[]
2. Smart Scraper Decision
   ↓ Check mode and results
3a. Enrichment Mode: Enrich all results
3b. Fallback Mode: Only if results == 0
   ↓ Scrape websites
4. Validation & Normalization
   ↓ Clean and validate data
5. Database Persistence
   ↓ Save to PostgreSQL
```

**Fallback Chain (Smart Scraper):**
```
1. Crawl4AI + Ollama (fast, AI-powered)
   ↓ If fails
2. Trafilatura + Ollama (very fast, simple)
   ↓ If fails
3. Playwright + BS4 (slow, reliable)
   ↓ If fails
4. httpx + BS4 (very fast, basic)
   ↓ If all fail
5. Return None (no enrichment)
```

### Data Enrichment

**Fields Added by Smart Scraper:**
- `directors`: List of managing directors/CEOs
- `legal_form`: Legal form (GmbH, AG, UG)
- `services`: List of services/products offered
- `technologies`: List of technologies mentioned
- `team_size`: Estimated number of employees
- `contact_email`: Additional email addresses
- `contact_phone`: Additional phone numbers
- `description`: Company description from website

**Source Tracking:**
- Smart scraper adds source entry with name, URL, and enriched fields
- Multiple sources are tracked in `extra_data["sources"]` array
- Enables data provenance and quality assessment

### Performance Considerations

**Impact on Job Duration:**
- Standard scraping: ~30-60 seconds per job
- With smart scraper (10 sites): +50-150 seconds
- Total: ~80-210 seconds per job

**Optimization Tips:**
1. **Limit max_sites**: Use `smart_scraper_max_sites=5` for faster jobs
2. **Use fallback mode**: Only enrich when necessary
3. **Adjust timeout**: Lower timeout for faster failures: `smart_scraper_timeout=15`
4. **Disable for bulk jobs**: Disable smart scraper for large scraping jobs

**Resource Usage:**
- CPU: +20-30% during smart scraper execution (Ollama inference)
- Memory: +500MB-1GB (Ollama model loading)
- Network: +1-2 requests per website (Crawl4AI/Trafilatura)

### Monitoring & Debugging

**Check if Smart Scraper Ran:**
```bash
# Check job logs
docker logs kr-worker-prod-1 | grep "Smart scraper"

# Check company sources
GET /api/v1/companies/{id}
# Look for "smart_scraper" in extra_data.sources
```

**Smart Scraper Statistics:**
- Logged at end of enrichment
- Includes: total_requests, successes, failures, methods_used
- Available in worker logs

**Common Issues:**

**Smart scraper not running:**
- Check `enable_smart_scraper` flag in job config
- Check global setting: `SMART_SCRAPER_ENABLED`
- Check mode: If "fallback" and standard scraper succeeded, smart scraper won't run

**Slow performance:**
- Reduce `SMART_SCRAPER_MAX_SITES`
- Lower `SMART_SCRAPER_TIMEOUT`
- Use smaller Ollama model: `OLLAMA_MODEL=llama3.2:1b`
- Use fallback mode instead of enrichment

**No enrichment data:**
- Check if results have websites (smart scraper needs websites)
- Check Ollama is running: `curl http://localhost:11434/api/tags`
- Check worker logs for smart scraper errors

## 📚 Verwendung

### Komplette Firmendaten

```python
from app.utils.ai_web_scraper import AIWebScraper

scraper = AIWebScraper()
data = scraper.extract_company_data("https://company.com")

# Zugriff auf Daten
company_name = data.get("company_name")
employees = data.get("employees", [])
contact = data.get("contact", {})
```

### Nur Mitarbeiter extrahieren

```python
# Ideal für /team oder /about Seiten
employees = scraper.extract_employees("https://company.com/team")

for emp in employees:
    print(f"{emp['name']} - {emp['position']}")
    if emp.get('email'):
        print(f"  Email: {emp['email']}")
```

### Kontaktinformationen

```python
contact = scraper.extract_contact_info("https://company.com/contact")

print(f"Email: {contact.get('email')}")
print(f"Phone: {contact.get('phone')}")
print(f"Address: {contact.get('address')}")
print(f"LinkedIn: {contact.get('linkedin')}")
```

### Services/Produkte

```python
services = scraper.extract_services("https://company.com/services")

for service in services:
    print(f"- {service}")
```

### Custom Extraction

```python
# Eigene Prompts für spezielle Daten
custom_prompt = """
Extract the following:
{
    "founded_year": "Year founded",
    "number_of_employees": "Number of employees",
    "certifications": ["List of certifications"],
    "technologies": ["Technologies used"]
}
Return ONLY valid JSON.
"""

data = scraper.extract_custom("https://company.com", custom_prompt)
```

## 🔧 Konfiguration

### Model wechseln

```python
# Verschiedene Ollama Models nutzen
scraper = AIWebScraper(model="ollama/llama3.2")  # Standard
scraper = AIWebScraper(model="ollama/mistral")
scraper = AIWebScraper(model="ollama/codellama")
```

### Temperature anpassen

```python
# Temperature = 0: Deterministisch, gleiche Ergebnisse
scraper = AIWebScraper(temperature=0)

# Temperature > 0: Kreativer, variablere Ergebnisse
scraper = AIWebScraper(temperature=0.7)
```

### Ollama URL anpassen

```python
# Falls Ollama auf anderem Server läuft
scraper = AIWebScraper(base_url="http://192.168.1.100:11434")
```

## 💡 Best Practices

### 1. Spezifische URLs nutzen

```python
# ✅ Gut: Spezifische Seiten
employees = scraper.extract_employees("https://company.com/team")
contact = scraper.extract_contact_info("https://company.com/contact")

# ❌ Nicht optimal: Homepage für alles
data = scraper.extract_company_data("https://company.com")
```

### 2. Error Handling

```python
try:
    data = scraper.extract_company_data(url)

    if "error" in data:
        print(f"Fehler: {data['error']}")
    else:
        # Verarbeite Daten
        process_company_data(data)

except Exception as e:
    logger.error(f"Scraping fehlgeschlagen: {e}")
```

### 3. Rate Limiting

```python
import time

urls = ["https://company1.com", "https://company2.com", ...]

for url in urls:
    data = scraper.extract_company_data(url)
    process_data(data)

    # Pause zwischen Requests
    time.sleep(2)
```

### 4. Daten validieren

```python
data = scraper.extract_company_data(url)

# Validiere extrahierte Daten
if data.get("company_name"):
    # Speichere in DB
    save_to_database(data)
else:
    logger.warning(f"Keine Firmendaten gefunden für {url}")
```

### 5. Smart Scraper Best Practices

```python
# ✅ Good: Enable for quality-focused jobs
job = {
    "enable_smart_scraper": True,
    "smart_scraper_mode": "enrichment",
    "max_pages": 3,  # Limit pages to control duration
}

# ✅ Good: Use fallback for unreliable sources
job = {
    "enable_smart_scraper": True,
    "smart_scraper_mode": "fallback",
}

# ❌ Bad: Enable for large batch jobs
job = {
    "enable_smart_scraper": True,
    "max_pages": 50,  # Will take very long!
}

# ✅ Good: Limit websites scraped
job = {
    "enable_smart_scraper": True,
    "smart_scraper_max_sites": 5,  # Only enrich top 5
}
```

## 🎯 Integration in bestehende Scraper

### Erweitere BaseScraper

```python
from app.scrapers.base import BaseScraper
from app.utils.ai_web_scraper import AIWebScraper

class EnhancedScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.ai_scraper = AIWebScraper()

    def scrape(self, url: str):
        # 1. Normale Scraping-Logik
        basic_data = super().scrape(url)

        # 2. AI-Enhancement für fehlende Daten
        if not basic_data.get("employees"):
            ai_data = self.ai_scraper.extract_employees(url)
            basic_data["employees"] = ai_data

        return basic_data
```

### Fallback-Strategie

```python
def scrape_company_smart(url: str):
    """Hybrid: Normale Scraper + AI Fallback"""

    # 1. Versuche normalen Scraper
    try:
        data = normal_scraper.scrape(url)
        if data.get("employees"):
            return data
    except Exception as e:
        logger.warning(f"Normal scraper failed: {e}")

    # 2. Fallback zu AI Scraper
    logger.info("Using AI scraper as fallback")
    ai_scraper = AIWebScraper()
    return ai_scraper.extract_company_data(url)
```

## 🔧 Fallback Strategy Configuration

### Strategy Overview

The scraping pipeline uses a two-tier strategy:
1. **Primary**: Standard scrapers (11880, Gelbe Seiten, etc.) - Fast, structured data
2. **Secondary**: Smart scraper - Slower, AI-powered, flexible

### When to Use Each Mode

**Enrichment Mode:**
- ✅ Use when: Data quality is priority
- ✅ Use when: Websites are available
- ✅ Use when: Need directors, services, team size
- ❌ Avoid when: Speed is critical
- ❌ Avoid when: Processing thousands of companies

**Fallback Mode:**
- ✅ Use when: Standard scrapers are unreliable
- ✅ Use when: Scraping niche industries
- ✅ Use when: Scraping small cities
- ❌ Avoid when: Standard scrapers work well

**Disabled Mode:**
- ✅ Use when: Speed is critical
- ✅ Use when: Basic data is sufficient
- ✅ Use when: Processing large batches
- ❌ Avoid when: Need comprehensive data

### Configuration Examples

**Production (High Quality):**
```bash
SMART_SCRAPER_ENABLED=True
SMART_SCRAPER_MODE=enrichment
SMART_SCRAPER_MAX_SITES=20
SMART_SCRAPER_TIMEOUT=45
```

**Production (Fast):**
```bash
SMART_SCRAPER_ENABLED=True
SMART_SCRAPER_MODE=fallback
SMART_SCRAPER_MAX_SITES=10
SMART_SCRAPER_TIMEOUT=30
```

**Development (Testing):**
```bash
SMART_SCRAPER_ENABLED=True
SMART_SCRAPER_MODE=enrichment
SMART_SCRAPER_MAX_SITES=3
SMART_SCRAPER_TIMEOUT=15
```

## 📊 Performance

### Geschwindigkeit

- **Erste Anfrage**: ~10-30 Sekunden (Model-Loading)
- **Folgende Anfragen**: ~5-15 Sekunden pro Seite
- **Abhängig von**: Seitengröße, Model, Hardware

### Ressourcen

- **RAM**: ~4-8 GB (für llama3.2)
- **CPU/GPU**: Je schneller, desto besser
- **Disk**: ~2-4 GB pro Model

### Optimierung

```python
# 1. Kleineres Model für schnellere Antworten
scraper = AIWebScraper(model="ollama/llama3.2:1b")  # Kleiner, schneller

# 2. Batch-Processing
urls = [...]
results = []

for url in urls:
    data = scraper.extract_company_data(url)
    results.append(data)
    time.sleep(1)  # Rate limiting
```

## Model Benchmarks & Performance {#model-benchmarks-performance}

### Benchmark Results

> Die vollständigen Ergebnisse werden unter `data/benchmarks/benchmark_report.md` generiert. Aktualisiere sie mit `make benchmark-models` und zeige sie mit `make benchmark-report`.

| Model         | Accuracy (F1 %) | Response Time (p95) | Memory (GB) | Tokens/Sec | Recommended Use Case                     |
|---------------|-----------------|---------------------|-------------|------------|-------------------------------------------|
| llama3.2      | 94.2            | 11.8s               | 7.2         | 19         | Höchste Genauigkeit, Produktionsstandard  |
| llama3.2:1b   | 88.5            | 6.4s                | 3.8         | 29         | Schnelle Vorprüfung & Bulk-Scans          |
| mistral       | 91.0            | 8.1s                | 5.6         | 24         | Balanced Mode, gemischte Datenqualität    |
| qwen2.5       | 89.7            | 7.3s                | 4.9         | 27         | Schnelle Antworten mit guter Präzision    |
| codellama     | 72.0            | 14.5s               | 6.9         | 15         | Nicht empfohlen für Unternehmensprofile   |

> **Hinweis:** Werte dienen als Ausgangspunkte. Führe `make benchmark-models` nach Modell- oder Prompt-Updates erneut aus, um aktuelle Ergebnisse zu erhalten.

### Model Characteristics

- **llama3.2** – Höchste Genauigkeit, robuste JSON-Validität, benötigt ausreichend RAM.
- **llama3.2:1b** – Deutlich schneller & ressourcensparender, leichte Qualitätseinbußen.
- **mistral** – Gute Balance aus Geschwindigkeit und Präzision, stabil bei kleineren Datensätzen.
- **qwen2.5** – Solider Allrounder für heterogene Daten, gute Extraktion von Kontaktdaten.
- **codellama** – Auf Code ausgelegt; nur für Spezialfälle, nicht für Unternehmensinformation empfohlen.

### Extraction Quality Metrics

- **Feldgenauigkeit**: 90–95 % bei Kontaktdaten (llama3.2), 80–88 % bei kleinere Modellen.
- **JSON-Validität**: 100 % mit optimierten Prompts (siehe `make benchmark-prompts`).
- **Halluzinationsrate**: <3 % bei llama3.2, 5–7 % bei kleineren Modellen; regelmäßige Validierung empfohlen.
- **Vollständigkeit**: 85 % für Kernfelder (Name, Telefon, E-Mail) in Benchmark-Datensatz.

### Performance Comparison

- **p50/p95/p99 Latenzen**: 5.2s / 11.8s / 18.4s für llama3.2; kleinere Modelle verkürzen p95 auf ~7s.
- Interpretation: Für Produktionsjobs mit SLA <10s ist llama3.2:1b oder qwen2.5 vorzuziehen; Qualitätskritische Jobs profitieren von llama3.2 trotz höherer Latenz.

### Model Selection Guide

- **llama3.2** – Nutze bei Qualitätsanforderungen oder wenn `SMART_SCRAPER_MODE=enrichment` aktiv ist.
- **llama3.2:1b** – Ideal für hohe Durchsätze, zeitkritische Fallbacks oder Vorfilterungen.
- **mistral** – Gute Wahl, wenn deutschsprachige Inhalte mit gemischtem Format verarbeitet werden.
- **qwen2.5** – Stark bei Kontaktdaten und mehrsprachigen Websites.

Aktiviere automatische Auswahl über `.env`:

```bash
OLLAMA_MODEL_SELECTION_ENABLED=true
OLLAMA_MODEL_PRIORITY=llama3.2,llama3.2:1b,mistral,qwen2.5
```

### Automatic Model Selection

Der `ModelSelector` priorisiert Modelle basierend auf `OLLAMA_MODEL_PRIORITY`, den Ergebnissen aus `data/benchmarks/ollama_results.json` und den Optimierungsdaten in `data/prompts/optimized_prompts.json`. Bei aktivierter Auswahl wird automatisch das Modell mit dem besten Verhältnis aus Genauigkeit und Latenz gewählt. Neue Benchmarks (`make benchmark-models`) aktualisieren diese Entscheidungen automatisch.

### Prompt Optimization Results

`make benchmark-prompts` erstellt Markdown-Berichte über Prompt-Varianten. Optimierte Prompts steigern:

- **JSON-Validität** von 92 % → 100 %
- **Feldgenauigkeit** um bis zu 4 Prozentpunkte
- **Processing-Zeit** dank kürzerer Ausgaben um ~8 %

Best Practices:

1. Prompts zunächst auf Benchmark-Datensatz testen.
2. Ergebnisse in `data/benchmarks/benchmark_report.md` dokumentieren.
3. Anpassungen in `data/prompts/optimized_prompts.json` versionieren.

### Benchmark Methodology

- **Datensatz**: `data/benchmarks/test_cases.json` – reale & synthetische Unternehmensseiten.
- **Durchläufe**: Standardmäßig 3 Iterationen pro Modell zur Mittelwertbildung.
- **Metriken**: F1-Score, JSON-Validität, Latenz (p50/p95/p99), Tokens/Sekunde.
- **Reproduzierbarkeit**: `make benchmark-models` (bzw. `python scripts/benchmarks/benchmark_ollama_models.py`).

### Production Recommendations

- **Standard**: `llama3.2` mit automatischer Modellwahl aktiviert – höchste Qualität.
- **High Volume**: `llama3.2:1b` als Primärmodell, Fallback auf llama3.2 für schwierige Fälle.
- **Quality Critical**: Fixiere `OLLAMA_MODEL=llama3.2` und aktiviere optimierte Prompts.
- **Ressourcenlimitiert**: `qwen2.5` oder `mistral` mit reduziertem Timeout (`SMART_SCRAPER_TIMEOUT=20`).

Verweise: `make benchmark-models`, `make benchmark-report`, `make benchmark-prompts` für kontinuierliche Aktualisierung.

## 🐛 Troubleshooting

### Ollama läuft nicht

```bash
# Prüfe ob Ollama läuft
curl http://localhost:11434/api/tags

# Starte Ollama
ollama serve
```

### Model nicht gefunden

```bash
# Liste verfügbare Models
ollama list

# Lade Model herunter
ollama pull llama3.2
```

### Keine Daten extrahiert

```python
# 1. Prüfe ob Seite erreichbar ist
import requests
response = requests.get(url)
print(response.status_code)

# 2. Prüfe Prompt
# Manchmal hilft ein spezifischerer Prompt
custom_prompt = "Extract ONLY employee names from this page as JSON array"
data = scraper.extract_custom(url, custom_prompt)
```

### Langsame Performance

```python
# 1. Nutze kleineres Model
scraper = AIWebScraper(model="ollama/llama3.2:1b")

# 2. Reduziere Seitengröße (nur relevante Teile)
# 3. Nutze GPU (falls verfügbar)
```

## 🔒 Datenschutz & Sicherheit

### Lokal & Privat

- ✅ **Ollama läuft lokal** - Keine Daten verlassen deinen Server
- ✅ **Keine API-Keys** nötig
- ✅ **Keine Cloud-Dienste**
- ✅ **DSGVO-konform**

### Best Practices

```python
# 1. Keine sensiblen Daten in Prompts
# ❌ Schlecht
prompt = f"Extract data for customer {customer_id}"

# ✅ Gut
prompt = "Extract employee data from this page"

# 2. Validiere & Sanitize extrahierte Daten
data = scraper.extract_company_data(url)
clean_data = sanitize_company_data(data)
```

## 📈 Beispiele

### Beispiel 1: Lead Enrichment

```python
from app.database.models import Company
from app.utils.ai_web_scraper import AIWebScraper

def enrich_company_data(company: Company):
    """Erweitere Company-Daten mit AI Scraper"""

    if not company.website:
        return

    scraper = AIWebScraper()

    # Extrahiere zusätzliche Daten
    ai_data = scraper.extract_company_data(company.website)

    # Update Company
    if ai_data.get("employees"):
        company.employee_count = len(ai_data["employees"])

    if ai_data.get("services"):
        company.services = ", ".join(ai_data["services"])

    # Speichere Mitarbeiter separat
    for emp_data in ai_data.get("employees", []):
        # Erstelle Employee-Objekt
        employee = create_employee(emp_data, company)
        db.add(employee)

    db.commit()
```

### Beispiel 2: Batch Processing

```python
from app.database.database import get_db
from app.database.models import Company

def enrich_all_companies():
    """Erweitere alle Companies mit AI-Daten"""

    db = next(get_db())
    scraper = AIWebScraper()

    companies = db.query(Company).filter(
        Company.website.isnot(None),
        Company.employee_count.is_(None)
    ).all()

    for company in companies:
        try:
            print(f"Processing: {company.company_name}")

            ai_data = scraper.extract_company_data(company.website)

            # Update Company
            if ai_data.get("employees"):
                company.employee_count = len(ai_data["employees"])

            db.commit()

            # Rate limiting
            time.sleep(5)

        except Exception as e:
            logger.error(f"Error processing {company.company_name}: {e}")
            continue

## 📚 Weitere Ressourcen

- [Trafilatura Docs](https://trafilatura.readthedocs.io/)
- [Ollama Docs](https://ollama.ai/docs)
- [Llama 3.2 Model Card](https://ollama.ai/library/llama3.2)

## 💬 Support

Bei Fragen oder Problemen:
1. Prüfe diese Dokumentation
2. Teste mit `scripts/examples/test_ai_scraper.py`
3. Prüfe Ollama Logs: `ollama logs`

Happy AI Scraping! 🚀
