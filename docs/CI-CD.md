# CI/CD Pipeline - GitHub Actions

Dieses Projekt nutzt GitHub Actions für Continuous Integration und Continuous Deployment.

## 🎯 Workflows

### 1. Tests Workflow (`tests.yml`)

**Trigger:**
- Push zu `main` oder `develop` Branch
- Pull Requests zu `main` oder `develop`

**Was wird getestet:**
- ✅ 52 Integration Tests
- ✅ PostgreSQL Integration
- ✅ Redis Integration
- ✅ Code Coverage Report

**Services:**
- PostgreSQL 15
- Redis 7

**Schritte:**
1. Code auschecken
2. Python 3.13 installieren
3. Dependencies installieren
4. Tests ausführen mit Coverage
5. Coverage Report hochladen (Codecov)

**Dauer:** ~5 Minuten

### 2. Code Quality Workflow (`code-quality.yml`)

**Trigger:**
- Push zu `main` oder `develop` Branch
- Pull Requests zu `main` oder `develop`

**Checks:**
- ✅ **Black** - Code Formatting
- ✅ **isort** - Import Sorting
- ✅ **Flake8** - Linting & Style Guide
- ✅ **mypy** - Type Checking

**Dauer:** ~2 Minuten

### 3. Security Workflow (`security.yml`)

**Trigger:**
- Push zu `main` oder `develop` Branch
- Pull Requests zu `main` oder `develop`
- Wöchentlich (Montags 00:00 UTC)

**Scans:**
- ✅ **Bandit** - Security Vulnerability Scanner
- ✅ **Safety** - Dependency Vulnerability Check

**Dauer:** ~3 Minuten

## 📊 Status Badges

Die Badges im README zeigen den aktuellen Status:

```markdown
[![Tests](https://github.com/YOUR_USERNAME/KR-Lead-Scraper/actions/workflows/tests.yml/badge.svg)](...)
[![Code Quality](https://github.com/YOUR_USERNAME/KR-Lead-Scraper/actions/workflows/code-quality.yml/badge.svg)](...)
[![Security](https://github.com/YOUR_USERNAME/KR-Lead-Scraper/actions/workflows/security.yml/badge.svg)](...)
```

**Status:**
- ✅ Grün = Alle Checks bestanden
- ❌ Rot = Mindestens ein Check fehlgeschlagen
- 🟡 Gelb = Workflow läuft gerade

## 🔧 Konfiguration

### Environment Variables

Die Workflows nutzen folgende Environment Variables:

```yaml
DATABASE_URL: postgresql://postgres:postgres@localhost:5432/kr_leads_test
REDIS_URL: redis://localhost:6379/0
SECRET_KEY: test-secret-key-for-github-actions-min-32-chars
DEBUG: false
SENTRY_ENABLED: false
```

### Secrets (für Production)

Für Production-Deployments können GitHub Secrets genutzt werden:

1. Gehe zu Repository Settings → Secrets and variables → Actions
2. Füge Secrets hinzu:
   - `DATABASE_URL` - Production Database URL
   - `SECRET_KEY` - Production Secret Key
   - `SENTRY_DSN` - Sentry DSN für Error Tracking

## 📈 Coverage Reports

### Codecov Integration

Coverage Reports werden automatisch zu Codecov hochgeladen:

1. Gehe zu [codecov.io](https://codecov.io)
2. Verbinde dein GitHub Repository
3. Coverage Reports erscheinen automatisch bei jedem Push

### Lokale Coverage

```bash
# Coverage lokal ausführen
pytest tests/ --cov=app --cov-report=html

# Report öffnen
open htmlcov/index.html
```

## 🚀 Workflow-Beispiele

### Erfolgreicher Workflow

```
✅ Tests (5m 23s)
  ✓ Checkout code
  ✓ Set up Python 3.13
  ✓ Install dependencies
  ✓ Run tests with coverage
    → 52 passed, 0 failed
  ✓ Upload coverage to Codecov
```

### Fehlgeschlagener Workflow

```
❌ Tests (3m 45s)
  ✓ Checkout code
  ✓ Set up Python 3.13
  ✓ Install dependencies
  ✗ Run tests with coverage
    → 49 passed, 3 failed
    → test_api_companies.py::test_create_company FAILED
```

## 🔄 Pull Request Workflow

### 1. Branch erstellen
```bash
git checkout -b feature/new-feature
```

### 2. Code schreiben & committen
```bash
git add .
git commit -m "feat: Add new feature"
```

### 3. Push zu GitHub
```bash
git push origin feature/new-feature
```

### 4. Pull Request erstellen
- GitHub Actions läuft automatisch
- Alle Checks müssen bestehen (✅)
- Erst dann kann gemerged werden

### 5. Merge nach Approval
```bash
# Nach Review und grünen Checks
git checkout main
git merge feature/new-feature
```

## 🛠️ Lokale Entwicklung

### Pre-Commit Checks

Installiere Pre-Commit Hooks für lokale Checks:

```bash
# Pre-commit installieren
pip install pre-commit

# Hooks installieren
pre-commit install

# Manuell ausführen
pre-commit run --all-files
```

### Lokale Tests vor Push

```bash
# Tests ausführen
pytest tests/ -v

# Code Quality Checks
black --check app/ tests/
isort --check-only app/ tests/
flake8 app/ tests/

# Security Scan
bandit -r app/
```

## 📝 Workflow Customization

### Tests nur für bestimmte Dateien

```yaml
on:
  push:
    paths:
      - 'app/**'
      - 'tests/**'
      - 'requirements.txt'
```

### Matrix Testing (mehrere Python Versionen)

```yaml
strategy:
  matrix:
    python-version: ['3.11', '3.12', '3.13']
```

### Conditional Steps

```yaml
- name: Deploy to Production
  if: github.ref == 'refs/heads/main' && github.event_name == 'push'
  run: |
    # Deployment commands
```

## 🎯 Best Practices

### 1. Commit Messages

Nutze Conventional Commits:

```bash
feat: Add new scraper for Handelsregister
fix: Fix authentication bug in Companies API
docs: Update API documentation
test: Add tests for scraping endpoints
refactor: Improve database query performance
```

### 2. Branch Protection

Aktiviere Branch Protection für `main`:

1. Settings → Branches → Add rule
2. Branch name pattern: `main`
3. ✅ Require status checks to pass
4. ✅ Require pull request reviews
5. ✅ Require linear history

### 3. Code Review

Vor dem Merge:
- ✅ Alle Tests bestehen
- ✅ Code Review von mindestens 1 Person
- ✅ Keine merge conflicts
- ✅ Documentation aktualisiert

## 🐛 Troubleshooting

### Workflow schlägt fehl

**Problem:** Tests schlagen fehl

**Lösung:**
1. Logs in GitHub Actions anschauen
2. Fehler lokal reproduzieren
3. Fix committen und pushen
4. Workflow läuft automatisch erneut

### Dependency Conflicts

**Problem:** `pip install` schlägt fehl

**Lösung:**
```bash
# requirements.txt aktualisieren
pip freeze > requirements.txt

# Oder spezifische Versionen pinnen
fastapi==0.118.0
sqlalchemy==2.0.23
```

### Timeout Issues

**Problem:** Workflow läuft zu lange (>6h)

**Lösung:**
```yaml
jobs:
  test:
    timeout-minutes: 30  # Max 30 Minuten
```

## 📊 Monitoring

### Workflow Runs anschauen

1. Gehe zu GitHub Repository
2. Tab "Actions"
3. Wähle Workflow aus
4. Siehe alle Runs mit Status

### Notifications

GitHub benachrichtigt automatisch bei:
- ❌ Fehlgeschlagenen Workflows
- ✅ Erfolgreichen Workflows (optional)

**Email Notifications konfigurieren:**
1. GitHub Settings → Notifications
2. Actions → Configure
3. Wähle Notification-Präferenzen

## 🚀 Deployment Workflow (Optional)

Für automatisches Deployment:

```yaml
name: Deploy

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: github.event_name == 'push'

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Deploy to Production
      env:
        DEPLOY_KEY: ${{ secrets.DEPLOY_KEY }}
      run: |
        # SSH to server
        # Pull latest code
        # Restart services
```

## 📚 Weitere Ressourcen

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Workflow Syntax](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions)
- [Codecov Documentation](https://docs.codecov.com/)
- [Pre-commit Hooks](https://pre-commit.com/)

## 💡 Tipps

### Schnellere Workflows

1. **Caching nutzen:**
```yaml
- uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
```

2. **Parallele Jobs:**
```yaml
jobs:
  test:
    strategy:
      matrix:
        test-group: [unit, integration, e2e]
```

3. **Conditional Steps:**
```yaml
- name: Run expensive test
  if: github.event_name == 'push' && github.ref == 'refs/heads/main'
```

### Kosten sparen

- ✅ Nutze `continue-on-error: true` für nicht-kritische Checks
- ✅ Limitiere Workflow-Runs mit `concurrency`
- ✅ Nutze Caching für Dependencies
- ✅ Teste nur geänderte Dateien (mit `paths` Filter)

## 🎉 Fertig!

Deine CI/CD Pipeline ist jetzt eingerichtet! 🚀

Bei jedem Push:
1. ✅ Tests laufen automatisch
2. ✅ Code Quality wird geprüft
3. ✅ Security Scans laufen
4. ✅ Du siehst sofort den Status

**Happy Coding!** 💻
