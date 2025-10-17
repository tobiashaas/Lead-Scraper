# Contributing to KR-Lead-Scraper

Vielen Dank für dein Interesse, zu diesem Projekt beizutragen! 🎉

## 🚀 Quick Start

### 1. Repository forken & clonen

```bash
# Fork auf GitHub erstellen, dann:
git clone https://github.com/YOUR_USERNAME/KR-Lead-Scraper.git
cd KR-Lead-Scraper
```

### 2. Development Environment einrichten

```bash
# Virtual Environment erstellen
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate  # Windows

# Dependencies installieren
pip install -r requirements.txt

# Pre-commit hooks installieren
pip install pre-commit
pre-commit install
```

### 3. Branch erstellen

```bash
git checkout -b feature/deine-neue-feature
```

### 4. Code schreiben & testen

```bash
# Tests ausführen
pytest tests/ -v

# Code Quality Checks
black --check app/ tests/
flake8 app/ tests/

# Oder alle Pre-commit Checks
pre-commit run --all-files
```

### 5. Committen & Pushen

```bash
git add .
git commit -m "feat: Add new feature"
git push origin feature/deine-neue-feature
```

### 6. Pull Request erstellen

1. Gehe zu GitHub
2. Erstelle Pull Request von deinem Branch
3. Warte auf CI/CD Checks (müssen grün sein ✅)
4. Warte auf Code Review

## 📝 Commit Message Guidelines

Wir nutzen [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Feature
git commit -m "feat: Add new scraper for Handelsregister"

# Bug Fix
git commit -m "fix: Fix authentication bug in Companies API"

# Documentation
git commit -m "docs: Update API documentation"

# Tests
git commit -m "test: Add tests for scraping endpoints"

# Refactoring
git commit -m "refactor: Improve database query performance"

# Style
git commit -m "style: Format code with Black"

# Chore
git commit -m "chore: Update dependencies"
```

**Format:**
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: Neue Feature
- `fix`: Bug Fix
- `docs`: Dokumentation
- `style`: Code-Formatierung
- `refactor`: Code-Refactoring
- `test`: Tests
- `chore`: Maintenance

## 🧪 Testing

### Unit Tests

```bash
# Alle Tests
pytest tests/

# Spezifischer Test
pytest tests/integration/test_api_companies.py

# Mit Coverage
pytest tests/ --cov=app --cov-report=html
```

### Integration Tests

```bash
# Benötigt PostgreSQL & Redis
docker-compose up -d postgres redis

# Tests ausführen
pytest tests/integration/ -v
```

### Test-Struktur

```python
def test_feature_name():
    """Test: Beschreibung was getestet wird"""
    # Arrange
    setup_data()
    
    # Act
    result = function_to_test()
    
    # Assert
    assert result == expected_value
```

## 🎨 Code Style

### Python Style Guide

Wir folgen [PEP 8](https://pep8.org/) mit einigen Anpassungen:

- **Line Length**: 127 Zeichen (nicht 79)
- **Formatter**: Black
- **Linter**: Flake8
- **Type Hints**: Empfohlen, aber nicht zwingend

### Automatische Formatierung

```bash
# Black (Code Formatter)
black app/ tests/

# isort (Import Sorting)
isort app/ tests/

# Alle Checks
pre-commit run --all-files
```

### Type Hints

```python
# ✅ Gut
def get_company(company_id: int) -> Company:
    return db.query(Company).filter(Company.id == company_id).first()

# ❌ Nicht so gut
def get_company(company_id):
    return db.query(Company).filter(Company.id == company_id).first()
```

## 📚 Documentation

### Docstrings

Nutze Google-Style Docstrings:

```python
def scrape_companies(city: str, industry: str) -> List[Company]:
    """
    Scrape companies from Gelbe Seiten.
    
    Args:
        city: City name (e.g. "Stuttgart")
        industry: Industry name (e.g. "IT-Services")
    
    Returns:
        List of Company objects
    
    Raises:
        ScraperError: If scraping fails
    
    Example:
        >>> companies = scrape_companies("Stuttgart", "IT")
        >>> len(companies)
        42
    """
    pass
```

### README Updates

Bei neuen Features:
1. ✅ README.md aktualisieren
2. ✅ Docs-Ordner aktualisieren
3. ✅ Beispiele hinzufügen

## 🔒 Security

### Secrets & Keys

**NIEMALS committen:**
- ❌ API Keys
- ❌ Passwörter
- ❌ Database URLs
- ❌ Secret Keys

**Stattdessen:**
- ✅ `.env` Datei nutzen (ist in `.gitignore`)
- ✅ Environment Variables
- ✅ GitHub Secrets für CI/CD

### Security Scans

```bash
# Bandit (Security Scanner)
bandit -r app/

# Safety (Dependency Check)
safety check
```

## 🐛 Bug Reports

### Issue erstellen

1. Gehe zu [Issues](https://github.com/YOUR_USERNAME/KR-Lead-Scraper/issues)
2. Klicke "New Issue"
3. Nutze Template:

```markdown
**Beschreibung:**
Kurze Beschreibung des Bugs

**Schritte zum Reproduzieren:**
1. Schritt 1
2. Schritt 2
3. Bug tritt auf

**Erwartetes Verhalten:**
Was sollte passieren

**Aktuelles Verhalten:**
Was passiert tatsächlich

**Environment:**
- OS: Windows 11
- Python: 3.13
- Version: 1.0.0

**Logs:**
```
Error logs hier
```
```

## ✨ Feature Requests

### Feature vorschlagen

1. Erstelle Issue mit Label "enhancement"
2. Beschreibe:
   - Was soll die Feature machen?
   - Warum ist sie nützlich?
   - Wie könnte sie implementiert werden?

## 🔄 Pull Request Process

### 1. Vor dem PR

- ✅ Alle Tests bestehen lokal
- ✅ Code ist formatiert (Black)
- ✅ Keine Linting-Fehler
- ✅ Documentation aktualisiert
- ✅ Commit Messages folgen Convention

### 2. PR erstellen

**Titel:**
```
feat: Add new scraper for Handelsregister
```

**Beschreibung:**
```markdown
## Änderungen
- Added new scraper for Handelsregister
- Added tests for new scraper
- Updated documentation

## Testing
- [x] Unit tests pass
- [x] Integration tests pass
- [x] Manual testing done

## Screenshots (optional)
![Screenshot](url)

## Related Issues
Closes #123
```

### 3. Nach dem PR

- ✅ CI/CD Checks müssen grün sein
- ✅ Code Review abwarten
- ✅ Feedback umsetzen
- ✅ Merge durch Maintainer

## 👥 Code Review

### Als Reviewer

**Worauf achten:**
- ✅ Code-Qualität
- ✅ Tests vorhanden
- ✅ Documentation aktualisiert
- ✅ Keine Breaking Changes (ohne Diskussion)
- ✅ Performance-Implikationen

**Feedback geben:**
```markdown
# ✅ Gut
Great implementation! Just one small suggestion:
Could you add a docstring to this function?

# ❌ Nicht so gut
This is wrong.
```

### Als Author

**Auf Feedback reagieren:**
- ✅ Konstruktiv annehmen
- ✅ Fragen stellen bei Unklarheiten
- ✅ Änderungen umsetzen
- ✅ "Resolved" markieren nach Fix

## 🎯 Best Practices

### 1. Small PRs

```
✅ Gut: 1 Feature, 200 Zeilen
❌ Schlecht: 5 Features, 2000 Zeilen
```

### 2. Atomic Commits

```bash
# ✅ Gut
git commit -m "feat: Add Company model"
git commit -m "test: Add tests for Company model"
git commit -m "docs: Update API documentation"

# ❌ Schlecht
git commit -m "Add everything"
```

### 3. Tests schreiben

```python
# Für jede neue Funktion:
def new_feature():
    pass

# Schreibe Test:
def test_new_feature():
    assert new_feature() == expected
```

### 4. Documentation

```python
# Für jede neue API:
@router.post("/companies/")
async def create_company():
    """
    Create a new company.
    
    - **company_name**: Name of the company
    - **city**: City where company is located
    """
    pass
```

## 📊 Project Structure

```
KR-Lead-Scraper/
├── app/
│   ├── api/              # FastAPI Endpoints
│   ├── core/             # Core functionality (config, security)
│   ├── database/         # Database models & migrations
│   ├── scrapers/         # Scraper implementations
│   ├── utils/            # Utilities (logger, rate limiter)
│   └── middleware/       # FastAPI middleware
├── tests/
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── docs/                 # Documentation
├── .github/
│   └── workflows/        # GitHub Actions
└── alembic/              # Database migrations
```

## 🆘 Hilfe bekommen

### Fragen stellen

1. **GitHub Discussions**: Für allgemeine Fragen
2. **Issues**: Für Bugs & Feature Requests
3. **Discord/Slack**: Für schnelle Hilfe (falls vorhanden)

### Ressourcen

- [FastAPI Docs](https://fastapi.tiangolo.com)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org)
- [Pytest Docs](https://docs.pytest.org)
- [GitHub Actions Docs](https://docs.github.com/en/actions)

## 📜 License

Durch Beiträge zu diesem Projekt stimmst du zu, dass deine Beiträge unter der MIT License lizenziert werden.

## 🎉 Danke!

Danke, dass du zu KR-Lead-Scraper beiträgst! 🚀

Jeder Beitrag, egal wie klein, wird geschätzt! 💙
