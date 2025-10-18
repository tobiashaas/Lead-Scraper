# Test Pull Request

This is a test PR to trigger all CI/CD workflows so that the status checks appear in the branch protection rules.

## Purpose
- Trigger all GitHub Actions workflows
- Make status checks visible in branch protection settings
- Test the CI/CD pipeline

## Workflows that will run:
- ✅ Tests (99 passing)
- ✅ Code Quality (Black, Ruff, isort, mypy)
- ✅ Security (Bandit)
- ✅ CI/CD Pipeline (Lint, Test, Security, Docker Build)

After this PR, you can configure the branch protection rules to require these status checks.

---

**This file can be deleted after branch protection is set up.**
