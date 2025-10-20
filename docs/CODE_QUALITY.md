# 🎨 Code Quality Guide

## Quick Commands

```bash
# Auto-fix all code quality issues
make fix

# Check code quality (without fixing)
make lint

# Format code with Black
make format
```

---

## Tools

### Black - Code Formatter
- **Purpose:** Consistent code formatting
- **Config:** `pyproject.toml`
- **Line length:** 100 characters

### Ruff - Fast Linter
- **Purpose:** Fast Python linter (replaces flake8, isort, etc.)
- **Config:** `pyproject.toml`
- **Rules:** Comprehensive Python best practices

---

## Manual Commands

### Black

```bash
# Check formatting
black --check .

# Auto-format
black .

# Check specific files
black --check app/api/

# Show diff
black --diff .
```

### Ruff

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Fix with unsafe fixes
ruff check --fix --unsafe-fixes .

# Format code (alternative to Black)
ruff format .
```

---

## Pre-commit Hooks

Install pre-commit hooks to automatically check code before commits:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.10.0
    hooks:
      - id: black
        language_version: python3.13

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

---

## CI/CD Integration

### GitHub Actions

The project includes automatic linting in CI/CD:

**`.github/workflows/lint.yml`**

This workflow:
- ✅ Runs on every push and PR
- ✅ Checks Black formatting
- ✅ Runs Ruff linting
- ✅ Fails if issues are found

**Fix CI failures:**
```bash
# Locally fix all issues
make fix

# Commit and push
git add .
git commit -m "style: Fix linting issues"
git push
```

---

## VS Code Integration

Add to `.vscode/settings.json`:

```json
{
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter",
    "editor.codeActionsOnSave": {
      "source.fixAll": true,
      "source.organizeImports": true
    }
  },
  "ruff.fixAll": true
}
```

**Required Extensions:**
- `ms-python.black-formatter`
- `charliermarsh.ruff`

---

## Common Issues

### 1. Line too long

**Error:**
```
line too long (120 > 100 characters)
```

**Fix:**
```python
# Bad
some_very_long_function_call(argument1, argument2, argument3, argument4, argument5)

# Good
some_very_long_function_call(
    argument1,
    argument2,
    argument3,
    argument4,
    argument5
)
```

### 2. Import sorting

**Error:**
```
I001 Import block is un-sorted or un-formatted
```

**Fix:**
```bash
# Ruff auto-fixes this
ruff check --fix .
```

### 3. Unused imports

**Error:**
```
F401 'module' imported but unused
```

**Fix:**
```bash
# Ruff auto-removes unused imports
ruff check --fix .
```

### 4. Dict comprehension

**Error:**
```
C416 Unnecessary dict comprehension
```

**Fix:**
```python
# Bad
result = {k: v for k, v in items}

# Good
result = dict(items)
```

---

## Configuration

### pyproject.toml

```toml
[tool.black]
line-length = 100
target-version = ['py313']
include = '\.pyi?$'

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]
ignore = [
    "E501",  # line too long (handled by black)
]
```

---

## Best Practices

### 1. Run before committing
```bash
make fix
git add .
git commit -m "your message"
```

### 2. Check before pushing
```bash
make lint
```

### 3. Use pre-commit hooks
```bash
pre-commit install
```

### 4. Format on save (VS Code)
Enable `editor.formatOnSave` in settings

### 5. CI/CD will catch issues
If you forget, GitHub Actions will remind you! 😉

---

## Troubleshooting

### Black and Ruff conflict

If Black and Ruff disagree on formatting:

```bash
# Black takes precedence
black .

# Then run Ruff
ruff check --fix .
```

### Pre-commit too slow

Skip pre-commit for quick commits:

```bash
git commit --no-verify -m "WIP"
```

**But remember to fix before pushing!**

### CI failing on formatting

```bash
# See what's wrong
make lint

# Fix everything
make fix

# Commit and push
git add .
git commit -m "style: Fix formatting"
git push
```

---

## Summary

| Command | Purpose | When to use |
|---------|---------|-------------|
| `make fix` | Auto-fix everything | Before committing |
| `make lint` | Check only | Before pushing |
| `make format` | Format code | Same as `make fix` |
| `make lint-ci` | CI/CD check | In GitHub Actions |

**Golden Rule:** Run `make fix` before every commit! 🎯
