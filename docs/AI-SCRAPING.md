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
