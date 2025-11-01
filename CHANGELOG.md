# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Automated CI/CD pipeline with GitHub Actions
- Blue-Green deployment for zero-downtime releases
- Staging environment for pre-production validation
- Comprehensive health checks and smoke tests
- Automatic rollback workflow for rapid recovery
- Deployment scripts (`deploy.sh`, `health_check.sh`, `rollback.sh`)
- Secrets management integration with AWS Secrets Manager and HashiCorp Vault

### Changed
- Updated deployment process to rely on automated workflows
- Enhanced health-check coverage with detailed dependency validation

### Fixed
- _N/A_

### Security
- Added vulnerability scanning with Trivy in deployment pipeline
- Integrated Bandit security scanning into CI

---

## [1.0.0] - YYYY-MM-DD

### Added
- Initial release of KR Lead Scraper
- Multi-source lead scraping (11880, Gelbe Seiten, etc.)
- RESTful API powered by FastAPI
- PostgreSQL database with Alembic migrations
- Redis caching and queueing support
- AI-powered data enrichment via Ollama
- JWT authentication and authorization
- Sentry error tracking integration
- Docker Compose setup for local development and production

### Changed
- _N/A_

### Fixed
- _N/A_

### Security
- _N/A_

---

## Template for New Releases

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes in existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Security fixes and improvements
```

---

## Guidelines

- **Added**: New features
- **Changed**: Updates to existing functionality
- **Deprecated**: Features scheduled for removal
- **Removed**: Deprecated features removed in this release
- **Fixed**: Bug fixes
- **Security**: Security-related fixes and improvements

### Version Format

- `MAJOR.MINOR.PATCH` (e.g., `1.2.3`)
- **MAJOR**: Breaking changes
- **MINOR**: Backward-compatible feature additions
- **PATCH**: Backward-compatible bug fixes

### Date Format

- Use ISO 8601 `YYYY-MM-DD`

### Helpful Links

- [Unreleased]: https://github.com/tobiashaas/Lead-Scraper/compare/v1.0.0...HEAD
- [1.0.0]: https://github.com/tobiashaas/Lead-Scraper/releases/tag/v1.0.0
