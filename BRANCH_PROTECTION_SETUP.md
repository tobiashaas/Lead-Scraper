# 🛡️ Branch Protection Setup Guide

## Schritt-für-Schritt Anleitung

### 1. Gehe zu GitHub Repository Settings

1. Öffne: https://github.com/tobiashaas/Lead-Scraper
2. Klicke auf **Settings** (oben rechts)
3. In der linken Sidebar: **Branches**

### 2. Branch Protection Rule erstellen

1. Klicke auf **Add branch protection rule**
2. Bei **Branch name pattern** eingeben: `main`

### 3. Empfohlene Einstellungen

#### ✅ Require a pull request before merging
- ☑️ **Require a pull request before merging**
  - ☑️ Require approvals: **1** (mindestens 1 Review erforderlich)
  - ☑️ Dismiss stale pull request approvals when new commits are pushed
  - ☑️ Require review from Code Owners (optional)

#### ✅ Require status checks to pass before merging
- ☑️ **Require status checks to pass before merging**
  - ☑️ Require branches to be up to date before merging
  - **Status checks die bestehen müssen:**
    - ✅ `Lint & Format Check` (CI/CD Pipeline)
    - ✅ `Test` (CI/CD Pipeline)
    - ✅ `Security Scan` (CI/CD Pipeline)
    - ✅ `Docker Build` (CI/CD Pipeline)
    - ✅ `Tests` (Tests Workflow)
    - ✅ `Code Quality` (Code Quality Workflow)
    - ✅ `Security` (Security Workflow)

#### ✅ Require conversation resolution before merging
- ☑️ **Require conversation resolution before merging**
  - Alle PR-Kommentare müssen resolved sein

#### ✅ Require signed commits (optional, aber empfohlen)
- ☑️ **Require signed commits**
  - Erhöht die Sicherheit

#### ✅ Require linear history (optional)
- ☑️ **Require linear history**
  - Verhindert Merge-Commits, nur Rebase/Squash erlaubt

#### ✅ Include administrators
- ☑️ **Include administrators**
  - Auch Admins müssen die Rules befolgen

#### ✅ Restrict who can push to matching branches (optional)
- Nur bestimmte Teams/Personen dürfen pushen

#### ✅ Allow force pushes
- ☐ **NICHT aktivieren!**
  - Force pushes sollten verboten sein

#### ✅ Allow deletions
- ☐ **NICHT aktivieren!**
  - Main Branch sollte nicht gelöscht werden können

### 4. Speichern

Klicke auf **Create** oder **Save changes**

---

## 🎯 Was das bewirkt:

### ✅ Vor jedem Merge auf `main`:
1. **Pull Request erforderlich** - Keine direkten Pushes
2. **1 Code Review erforderlich** - Mindestens 1 Approval
3. **Alle CI/CD Checks müssen grün sein:**
   - ✅ 99 Tests passing
   - ✅ Code Quality (Black, Ruff, isort, mypy)
   - ✅ Security Scan (Bandit)
   - ✅ Docker Build erfolgreich
4. **Alle Kommentare resolved** - Keine offenen Diskussionen
5. **Branch up-to-date** - Neueste Änderungen von main integriert

### 🚫 Verhindert:
- ❌ Direktes Pushen auf `main` ohne Review
- ❌ Mergen mit failing Tests
- ❌ Mergen mit Code Quality Issues
- ❌ Mergen mit Security Vulnerabilities
- ❌ Force Pushes auf `main`
- ❌ Löschen des `main` Branch

---

## 📝 Workflow nach Branch Protection:

### Für neue Features/Fixes:

```bash
# 1. Neuen Branch erstellen
git checkout -b feature/mein-feature

# 2. Änderungen machen
# ... code, code, code ...

# 3. Committen
git add .
git commit -m "feat: Mein neues Feature"

# 4. Pushen
git push origin feature/mein-feature

# 5. Pull Request auf GitHub erstellen
# - Gehe zu: https://github.com/tobiashaas/Lead-Scraper/pulls
# - Klicke "New Pull Request"
# - Base: main, Compare: feature/mein-feature
# - Beschreibung ausfüllen
# - "Create Pull Request"

# 6. Warten auf:
# - ✅ Alle CI/CD Checks grün
# - ✅ Code Review & Approval
# - ✅ Alle Kommentare resolved

# 7. Mergen
# - "Squash and merge" (empfohlen) oder "Merge pull request"
```

---

## 🎉 Vorteile:

- ✅ **Code Quality garantiert** - Nur getesteter Code kommt in main
- ✅ **Security garantiert** - Keine Vulnerabilities in main
- ✅ **Code Reviews** - Vier-Augen-Prinzip
- ✅ **Dokumentation** - Alle Änderungen in PRs dokumentiert
- ✅ **Rollback einfach** - Jeder PR ist ein sauberer Commit
- ✅ **CI/CD erzwungen** - Alle Checks müssen grün sein
- ✅ **Professional Workflow** - Industry Best Practices

---

## 🚀 Production Ready!

Nach dem Setup ist dein Repository:
- ✅ Enterprise-grade geschützt
- ✅ CI/CD Pipeline erzwungen
- ✅ Code Quality garantiert
- ✅ Security garantiert
- ✅ Professional Workflow
- ✅ Team-ready

**Dein Repository ist jetzt auf Production-Level! 🏆**
