# Sentry Error Tracking

Dieses Projekt nutzt Sentry für proaktives Error Tracking und Performance Monitoring.

## Features

- ✅ **Error Tracking** - Automatische Erfassung aller Exceptions
- ✅ **Performance Monitoring** - Transaction Tracking für API-Requests
- ✅ **User Context** - Verknüpfung von Errors mit Usern
- ✅ **Custom Context** - Zusätzliche Metadaten für besseres Debugging
- ✅ **Breadcrumbs** - Ereignis-Trail vor Errors
- ✅ **Release Tracking** - Versionierung von Deployments
- ✅ **Environment Separation** - Development, Staging, Production

## Setup

### 1. Sentry Account erstellen

1. Gehe zu [sentry.io](https://sentry.io) und erstelle einen kostenlosen Account
2. Erstelle ein neues Projekt (Python/FastAPI)
3. Kopiere den DSN (Data Source Name)

### 2. Konfiguration

Füge folgende Variablen zu deiner `.env` Datei hinzu:

```env
# Sentry Configuration
SENTRY_ENABLED=true
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=development
SENTRY_TRACES_SAMPLE_RATE=1.0
SENTRY_PROFILES_SAMPLE_RATE=1.0
```

**Wichtig:**
- `SENTRY_ENABLED=true` aktiviert Sentry
- `SENTRY_DSN` ist dein Projekt-DSN von Sentry
- `SENTRY_ENVIRONMENT` sollte je nach Umgebung angepasst werden (development, staging, production)
- Sample Rates (0.0-1.0) steuern, wie viele Events erfasst werden (1.0 = 100%)

### 3. Environment-spezifische Konfiguration

**Development:**
```env
SENTRY_ENABLED=true
SENTRY_ENVIRONMENT=development
SENTRY_TRACES_SAMPLE_RATE=1.0  # Alle Requests tracken
```

**Production:**
```env
SENTRY_ENABLED=true
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1  # 10% der Requests tracken (Performance)
```

## Verwendung

### Automatisches Error Tracking

Alle unbehandelten Exceptions werden automatisch an Sentry gesendet:

```python
# Dieser Error wird automatisch erfasst
def my_function():
    result = 1 / 0  # ZeroDivisionError -> Sentry
```

### Manuelles Error Capturing

```python
from app.core.sentry import capture_exception, capture_message

try:
    # Risky operation
    process_data()
except Exception as e:
    # Capture with custom context
    capture_exception(
        e,
        operation="data_processing",
        user_id=123,
        data_size=1000
    )
```

### Messages Senden

```python
from app.core.sentry import capture_message

capture_message(
    "Important event occurred",
    level="warning",
    event_type="business_logic",
    user_id=456
)
```

### User Context

```python
from app.core.sentry import set_user_context

# Nach User-Login
set_user_context(
    user_id=user.id,
    username=user.username,
    email=user.email,
    role=user.role.value
)
```

### Custom Context

```python
from app.core.sentry import set_context

# Scraping Job Context
set_context("scraping_job", {
    "job_id": job.id,
    "source": "gelbe_seiten",
    "city": "Stuttgart",
    "industry": "IT",
    "pages_scraped": 10
})

# Database Context
set_context("database", {
    "operation": "INSERT",
    "table": "companies",
    "rows_affected": 5
})
```

### Breadcrumbs

Breadcrumbs erstellen einen Trail von Ereignissen vor einem Error:

```python
from app.core.sentry import add_breadcrumb

add_breadcrumb("User logged in", category="auth", level="info")
add_breadcrumb("Navigated to dashboard", category="navigation", level="info")
add_breadcrumb("Started data export", category="action", level="info")
# ... Error occurs here
# Sentry zeigt alle Breadcrumbs vor dem Error
```

### Performance Monitoring

```python
from app.core.sentry import start_transaction

# Track komplette Operation
with start_transaction(name="scraping_job", op="scraping") as transaction:

    # Track einzelne Schritte
    with transaction.start_child(op="http", description="Fetch page") as span:
        response = fetch_page(url)

    with transaction.start_child(op="processing", description="Parse HTML") as span:
        data = parse_html(response)

    with transaction.start_child(op="db", description="Save results") as span:
        save_to_database(data)
```

## Integration in API Endpoints

### In FastAPI Endpoints

```python
from fastapi import APIRouter, Depends
from app.core.sentry import set_context, add_breadcrumb, capture_exception

router = APIRouter()

@router.post("/scraping/jobs")
async def create_scraping_job(job: ScrapingJobCreate):
    # Add context
    set_context("scraping_job", {
        "source": job.source_name,
        "city": job.city,
        "industry": job.industry
    })

    # Add breadcrumb
    add_breadcrumb(
        "Creating scraping job",
        category="api",
        level="info",
        data={"source": job.source_name}
    )

    try:
        # Create job
        db_job = create_job(job)
        return db_job
    except Exception as e:
        # Error wird automatisch erfasst mit Context
        raise
```

### In Background Tasks

```python
from app.core.sentry import start_transaction, set_context

async def run_scraping_job(job_id: int):
    with start_transaction(name="scraping_job", op="background_task") as transaction:

        set_context("job", {"job_id": job_id})

        with transaction.start_child(op="scraping", description="Scrape data"):
            results = scrape_data()

        with transaction.start_child(op="db", description="Save results"):
            save_results(results)
```

## Sentry Dashboard

### Issues (Errors)

Im Sentry Dashboard siehst du:

1. **Error Overview** - Alle Errors gruppiert nach Typ
2. **Error Details** - Stack Trace, Context, Breadcrumbs
3. **User Impact** - Wie viele User sind betroffen
4. **Frequency** - Wie oft tritt der Error auf
5. **First/Last Seen** - Wann wurde der Error erstmals/zuletzt gesehen

### Performance

1. **Transaction Overview** - Durchschnittliche Response Times
2. **Slow Transactions** - Langsamste Endpoints
3. **Throughput** - Requests pro Minute
4. **Apdex Score** - User Satisfaction Score

### Releases

Sentry tracked automatisch Releases basierend auf `app_version`:

```python
# In config.py
app_version: str = Field(default="1.0.0", description="Application Version")
```

## Best Practices

### 1. Aussagekräftige Error Messages

```python
# ❌ Schlecht
raise Exception("Error")

# ✅ Gut
raise ValueError(f"Invalid city '{city}' for source '{source}'")
```

### 2. Context hinzufügen

```python
# ❌ Ohne Context
capture_exception(e)

# ✅ Mit Context
capture_exception(
    e,
    operation="scraping",
    source="gelbe_seiten",
    city="Stuttgart",
    page=5
)
```

### 3. User Context setzen

```python
# Nach Login
set_user_context(
    user_id=user.id,
    username=user.username,
    email=user.email
)
```

### 4. Breadcrumbs nutzen

```python
# Wichtige Ereignisse als Breadcrumbs
add_breadcrumb("Started scraping", category="scraping")
add_breadcrumb("Fetched page 1", category="scraping")
add_breadcrumb("Parsing results", category="scraping")
# Error -> Breadcrumbs zeigen den Ablauf
```

### 5. Performance Monitoring

```python
# Langsame Operationen tracken
with start_transaction(name="data_export", op="export"):
    export_data()
```

## Alerts & Notifications

In Sentry kannst du Alerts konfigurieren:

1. **Email Alerts** - Bei neuen Errors
2. **Slack Integration** - Notifications in Slack
3. **Threshold Alerts** - Bei zu vielen Errors
4. **Performance Alerts** - Bei langsamen Endpoints

## Filtering

### Errors filtern

In `app/core/sentry.py` kannst du Errors filtern:

```python
def before_send_hook(event, hint):
    # Validation Errors nicht senden
    if 'exc_info' in hint:
        exc_type, exc_value, tb = hint['exc_info']
        if exc_type.__name__ == 'ValidationError':
            return None  # Event wird nicht gesendet

    return event
```

### Transactions filtern

```python
def before_send_transaction_hook(event, hint):
    # Health Checks nicht tracken
    if event.get('transaction', '').startswith('/health'):
        return None

    return event
```

## Kosten & Limits

Sentry hat verschiedene Pricing Tiers:

- **Developer (Free)**: 5.000 Events/Monat
- **Team**: 50.000 Events/Monat
- **Business**: 100.000+ Events/Monat

**Tipp:** Nutze Sample Rates in Production, um Kosten zu sparen:

```env
SENTRY_TRACES_SAMPLE_RATE=0.1  # Nur 10% der Requests tracken
```

## Troubleshooting

### Sentry sendet keine Events

1. Prüfe `SENTRY_ENABLED=true` in `.env`
2. Prüfe `SENTRY_DSN` ist korrekt
3. Prüfe Netzwerk-Verbindung zu sentry.io
4. Prüfe Logs: `Sentry initialized` sollte erscheinen

### Zu viele Events

1. Reduziere Sample Rates
2. Filtere unwichtige Errors in `before_send_hook`
3. Nutze Error Grouping in Sentry Dashboard

### Performance Issues

1. Reduziere `SENTRY_TRACES_SAMPLE_RATE`
2. Filtere Health Checks und andere häufige Requests
3. Nutze Async Sentry Client

## Testing

```bash
# Test Sentry Integration
python test_sentry.py

# Test mit echter API
# 1. Enable Sentry in .env
# 2. Start API: uvicorn app.main:app --reload
# 3. Trigger Error: curl http://localhost:8000/api/v1/trigger-error
# 4. Check Sentry Dashboard
```

## Weitere Ressourcen

- [Sentry Documentation](https://docs.sentry.io/)
- [Sentry Python SDK](https://docs.sentry.io/platforms/python/)
- [FastAPI Integration](https://docs.sentry.io/platforms/python/guides/fastapi/)
- [Performance Monitoring](https://docs.sentry.io/product/performance/)
