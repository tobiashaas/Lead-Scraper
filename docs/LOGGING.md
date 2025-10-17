# Structured Logging

Dieses Projekt nutzt strukturiertes JSON-basiertes Logging für bessere Auswertbarkeit und Monitoring.

## Features

- ✅ **JSON-Format** - Maschinenlesbare Logs für einfache Analyse
- ✅ **Correlation IDs** - Request-Tracking über mehrere Services
- ✅ **Request/Response Logging** - Automatisches Logging aller API-Requests
- ✅ **Structured Data** - Beliebige Felder als Key-Value-Pairs
- ✅ **Exception Tracking** - Vollständige Stack Traces in JSON
- ✅ **Performance Metrics** - Automatische Zeitmessung

## Verwendung

### Basic Logging

```python
from app.utils.structured_logger import get_structured_logger

logger = get_structured_logger(__name__)

# Simple message
logger.info("User logged in")

# With structured data
logger.info(
    "User logged in",
    user_id=123,
    username="john_doe",
    ip_address="192.168.1.100"
)

# Error logging
logger.error(
    "Database connection failed",
    error_code="DB001",
    host="localhost",
    port=5432
)

# Exception logging with traceback
try:
    result = 1 / 0
except Exception as e:
    logger.exception(
        "Division error",
        operation="divide",
        numerator=1,
        denominator=0
    )
```

### Correlation IDs

Correlation IDs werden automatisch von der Middleware gesetzt, können aber auch manuell verwendet werden:

```python
from app.utils.structured_logger import set_correlation_id, clear_correlation_id

# Set correlation ID
set_correlation_id("req-12345-abcde")

# All logs will now include this correlation ID
logger.info("Processing request")
logger.info("Database query")
logger.info("Request completed")

# Clear correlation ID
clear_correlation_id()
```

### Log Helpers

Für häufige Logging-Patterns gibt es Helper-Funktionen:

```python
from app.utils.log_helpers import (
    log_operation,
    log_function_call,
    log_api_request,
    log_database_query,
    log_scraping_job,
    log_authentication
)

# Context manager for operations
with log_operation("database_migration", version="001"):
    # Your code here
    pass

# Function decorator
@log_function_call
async def process_data(data):
    # Function will be automatically logged
    pass

# Specific logging functions
log_api_request("POST", "/api/users", 201, 123.45, user_id=456)
log_database_query("INSERT", "users", 12.3, rows_affected=1)
log_scraping_job(123, "gelbe_seiten", "completed", results=45)
log_authentication("login", "john_doe", True, ip="192.168.1.1")
```

## Log-Dateien

Das System schreibt in zwei Log-Dateien:

1. **logs/scraper.log** - Human-readable Format für Entwicklung
2. **logs/scraper_json.log** - JSON-Format für Produktion/Monitoring

### JSON Log Format

```json
{
  "timestamp": "2025-10-17T17:26:54.836865Z",
  "level": "INFO",
  "logger": "app.api.auth",
  "message": "User logged in",
  "module": "auth",
  "function": "login",
  "line": 99,
  "correlation_id": "req-12345-abcde",
  "user_id": 123,
  "username": "john_doe",
  "ip_address": "192.168.1.100"
}
```

## Request Logging

Die `LoggingMiddleware` loggt automatisch alle HTTP-Requests:

```json
{
  "timestamp": "2025-10-17T17:26:54.836865Z",
  "level": "INFO",
  "message": "Incoming request",
  "method": "POST",
  "path": "/api/v1/auth/login",
  "query_params": "",
  "client_host": "127.0.0.1",
  "user_agent": "Mozilla/5.0",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

```json
{
  "timestamp": "2025-10-17T17:26:55.123456Z",
  "level": "INFO",
  "message": "Request completed",
  "method": "POST",
  "path": "/api/v1/auth/login",
  "status_code": 200,
  "duration_ms": 287.12,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Log-Analyse

### Mit jq (Command Line)

```bash
# Alle ERROR-Logs
cat logs/scraper_json.log | jq 'select(.level == "ERROR")'

# Requests über 1 Sekunde
cat logs/scraper_json.log | jq 'select(.duration_ms > 1000)'

# Alle Logs für einen User
cat logs/scraper_json.log | jq 'select(.user_id == 123)'

# Correlation ID verfolgen
cat logs/scraper_json.log | jq 'select(.correlation_id == "req-12345")'

# Top 10 langsamste Requests
cat logs/scraper_json.log | jq 'select(.duration_ms) | {path, duration_ms}' | jq -s 'sort_by(.duration_ms) | reverse | .[0:10]'
```

### Mit Python

```python
import json

# Read and parse JSON logs
with open('logs/scraper_json.log') as f:
    logs = [json.loads(line) for line in f]

# Filter errors
errors = [log for log in logs if log['level'] == 'ERROR']

# Group by correlation ID
from collections import defaultdict
by_correlation = defaultdict(list)
for log in logs:
    if 'correlation_id' in log:
        by_correlation[log['correlation_id']].append(log)

# Analyze performance
durations = [log['duration_ms'] for log in logs if 'duration_ms' in log]
avg_duration = sum(durations) / len(durations)
```

## Best Practices

1. **Immer strukturierte Daten nutzen** - Statt `logger.info(f"User {user_id} logged in")` nutze `logger.info("User logged in", user_id=user_id)`

2. **Correlation IDs verwenden** - Für Request-Tracking über mehrere Services

3. **Sensitive Daten vermeiden** - Keine Passwörter, Tokens oder PII in Logs

4. **Aussagekräftige Messages** - Kurze, klare Beschreibungen

5. **Kontext hinzufügen** - Je mehr strukturierte Daten, desto besser die Analyse

6. **Log-Levels richtig nutzen**:
   - `DEBUG` - Detaillierte Informationen für Debugging
   - `INFO` - Normale Operationen
   - `WARNING` - Unerwartete Ereignisse, aber nicht kritisch
   - `ERROR` - Fehler, die behandelt werden müssen
   - `CRITICAL` - Schwere Fehler, die das System gefährden

## Monitoring Integration

Die JSON-Logs können einfach in Monitoring-Tools integriert werden:

- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Grafana Loki**
- **Datadog**
- **New Relic**
- **CloudWatch** (AWS)

Beispiel Logstash Config:

```ruby
input {
  file {
    path => "/path/to/logs/scraper_json.log"
    codec => "json"
  }
}

filter {
  # Add custom filters here
}

output {
  elasticsearch {
    hosts => ["localhost:9200"]
    index => "kr-leads-%{+YYYY.MM.dd}"
  }
}
```
