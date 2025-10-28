# GitHub Actions Workflows

Dieses Verzeichnis enthält alle CI/CD Workflows für das KR-Lead-Scraper Projekt.

## 📋 Verfügbare Workflows

### 1. Tests (`tests.yml`)
**Status:** [![Tests](https://github.com/YOUR_USERNAME/KR-Lead-Scraper/actions/workflows/tests.yml/badge.svg)](https://github.com/YOUR_USERNAME/KR-Lead-Scraper/actions/workflows/tests.yml)

- **Trigger:** Push/PR zu `main` oder `develop`
- **Dauer:** ~5 Minuten
- **Was:** 52 Integration Tests mit PostgreSQL & Redis
- **Coverage:** Automatischer Upload zu Codecov

### 2. Code Quality (`code-quality.yml`)
**Status:** [![Code Quality](https://github.com/YOUR_USERNAME/KR-Lead-Scraper/actions/workflows/code-quality.yml/badge.svg)](https://github.com/YOUR_USERNAME/KR-Lead-Scraper/actions/workflows/code-quality.yml)

- **Trigger:** Push/PR zu `main` oder `develop`
- **Dauer:** ~2 Minuten
- **Checks:** Black, isort, Flake8, mypy
- **Zweck:** Code-Stil und Qualität sicherstellen

### 3. Security (`security.yml`)
**Status:** [![Security](https://github.com/YOUR_USERNAME/KR-Lead-Scraper/actions/workflows/security.yml/badge.svg)](https://github.com/YOUR_USERNAME/KR-Lead-Scraper/actions/workflows/security.yml)

- **Trigger:** Push/PR + Wöchentlich (Montags)
- **Dauer:** ~3 Minuten
- **Scans:** Bandit (Code), Safety (Dependencies)
- **Zweck:** Sicherheitslücken finden

## 🚀 Schnellstart

### Lokale Tests vor Push

```bash
# Alle Tests ausführen
pytest tests/ -v

# Mit Coverage
pytest tests/ --cov=app --cov-report=html

# Code Quality Checks
black --check app/ tests/
flake8 app/ tests/
```

### Workflow Status prüfen

1. Gehe zu [Actions Tab](https://github.com/YOUR_USERNAME/KR-Lead-Scraper/actions)
2. Wähle Workflow aus
3. Siehe Details und Logs

## 📊 Workflow-Übersicht

```
Push/PR → GitHub
    ↓
┌───────────────────────────────────┐
│  Workflows starten automatisch    │
├───────────────────────────────────┤
│  ✅ Tests (5 min)                 │
│  ✅ Code Quality (2 min)          │
│  ✅ Security (3 min)              │
└───────────────────────────────────┘
    ↓
Alle grün? → Merge erlaubt ✅
Einer rot? → Fix erforderlich ❌
```

## 🔧 Konfiguration

### Environment Variables

Workflows nutzen diese Variablen:

```yaml
DATABASE_URL: postgresql://postgres:postgres@localhost:5432/kr_leads_test
REDIS_URL: redis://localhost:6379/0
SECRET_KEY: test-secret-key-for-github-actions-min-32-chars
DEBUG: false
SENTRY_ENABLED: false
```

### Secrets (Optional)

Für Production-Deployments:
- `DATABASE_URL` - Production DB
- `SECRET_KEY` - Production Secret
- `SENTRY_DSN` - Error Tracking

## 📝 Workflow bearbeiten

1. Datei öffnen (z.B. `tests.yml`)
2. Änderungen vornehmen
3. Committen und pushen
4. Workflow läuft automatisch mit neuer Config

## 🐛 Troubleshooting

### Workflow schlägt fehl

1. **Logs anschauen:**
   - Actions Tab → Workflow → Run → Job → Step

2. **Lokal reproduzieren:**
   ```bash
   pytest tests/ -v
   ```

3. **Fix committen:**
   ```bash
   git add .
   git commit -m "fix: Fix failing test"
   git push
   ```

### Workflow überspringen

Manchmal willst du Workflows überspringen (z.B. bei Doku-Änderungen):

```bash
git commit -m "docs: Update README [skip ci]"
```

## 📚 Weitere Infos

Siehe [CI-CD.md](../../docs/CI-CD.md) für ausführliche Dokumentation.

## 💡 Best Practices

1. ✅ Alle Tests lokal ausführen vor Push
2. ✅ Commit Messages nach Conventional Commits
3. ✅ Branch Protection für `main` aktivieren
4. ✅ Pull Requests nutzen (keine direkten Pushes zu `main`)
5. ✅ Code Reviews vor Merge

## 🎯 Nächste Schritte

Nach dem ersten Push:

1. ✅ Badges im README aktualisieren (Username ersetzen)
2. ✅ Branch Protection aktivieren
3. ✅ Codecov Account verbinden (optional)
4. ✅ Notifications konfigurieren

Happy Coding! 🚀
