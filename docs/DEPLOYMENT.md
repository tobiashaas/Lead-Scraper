# 🚀 Deployment Guide

## Overview

KR Lead Scraper uses automated CI/CD pipelines to deliver code safely to staging and production environments. Deployments are orchestrated by GitHub Actions and leverage container-based infrastructure for consistency and repeatability.

### Deployment Strategy

- **Staging**: Automatic rolling deployment on every push to the `develop` branch.
- **Production**: Automatic blue-green deployment on semantic version tags (`vMAJOR.MINOR.PATCH`).
- **Rollback**: Automated rollback on failure, with manual rollback workflow for emergencies.

### Environments

| Environment | URL | Trigger | Strategy |
|-------------|-----|---------|----------|
| Development | Local Docker (`docker-compose.yml`) | Manual | N/A |
| Staging | `https://staging.your-domain.com` | Push to `develop` | Rolling |
| Production | `https://api.your-domain.com` | Tag `v*.*.*` | Blue-Green |

## Quick Start

### Deploy to Staging

```bash
# Push changes to develop
git checkout develop
git push origin develop

# GitHub Actions will automatically build and deploy to staging
# Monitor the run at https://github.com/tobiashaas/Lead-Scraper/actions
```

### Deploy to Production

```bash
# Tag the release using semantic versioning
git checkout main
git tag v1.2.3
git push origin v1.2.3

# Production deployment workflow will execute automatically
# Monitor at https://github.com/tobiashaas/Lead-Scraper/actions
```

### Trigger Manual Rollback

```bash
# GitHub Actions UI
# 1. Navigate to Actions → "Manual Rollback"
# 2. Click "Run workflow"
# 3. Select environment (production/staging)
# 4. Enter target version (e.g., 1.2.2)
# 5. Provide rollback reason
# 6. Run workflow and monitor logs
```

## Deployment Workflows

### Staging Deployment (`.github/workflows/staging.yml`)

1. Build Docker image tagged `staging-{git-sha}` and `staging-latest`.
2. Push image to GitHub Container Registry (GHCR).
3. Deploy to staging server via SSH with rolling updates.
4. Execute health checks (5 retries, 30s interval).
5. Run integration and end-to-end tests against staging.
6. Upload test artifacts and notify via Slack/Discord.

### Production Deployment (`.github/workflows/deploy.yml`)

1. Validate semantic tag and ensure release is new.
2. Build Docker image for `v{version}` and `latest` tags.
3. Generate SBOM and perform vulnerability scan.
4. Deploy to production server using blue-green strategy.
5. Execute layered health checks and smoke tests.
6. Create GitHub Release and attach security artifacts.
7. Notify team of deployment result.

### Manual Rollback (`.github/workflows/rollback.yml`)

1. Validate target version exists in registry and releases.
2. Determine current deployed version on target environment.
3. Copy rollback utilities to server and run `rollback.sh`.
4. Execute health checks post-rollback.
5. Collect logs, create incident report issue, and notify team.

## Blue-Green Deployment

Blue-Green deployment keeps two identical production environments (Blue and Green). Only one serves traffic at a time.

1. Deploy new version to inactive container (e.g., Green).
2. Run health checks against inactive container.
3. Switch traffic from active (Blue) to inactive (Green) once healthy via nginx upstream symlink.
4. Verify symlink points to correct upstream configuration.
5. Stop old container and retain for quick rollback.
6. Alternate target on subsequent deployments.

**Advantages:** Zero downtime, instant rollback, consistent environment validation.

### Traffic Switching Mechanism

Production uses nginx upstream symlink switching for deterministic traffic routing:

- **Upstream Files**: `nginx/upstream-blue.conf` and `nginx/upstream-green.conf` define upstreams pointing to respective containers.
- **Active Symlink**: `nginx/upstream-active.conf` symlinks to the active upstream configuration.
- **Switch Process**: Deployment script updates symlink (`ln -sf upstream-{color}.conf upstream-active.conf`), verifies it, and reloads nginx.
- **Rollback**: On failure, symlink switches back to previous upstream automatically.

This approach ensures nginx routes traffic based on explicit configuration files rather than Docker labels, making the switching mechanism auditable and reliable.

See `nginx/README.md` for configuration details and `scripts/deployment/README.md` for deployment mechanics.

## Worker Deployment

RQ Worker-Container laufen parallel zu den API-Services und verarbeiten Scraping-Jobs aus der Redis Queue.

### Container-Setup

- **Development:** `docker-compose.yml` enthält den Service `worker`, der mit der gleichen Image/Codebasis wie die API gestartet wird.
- **Staging:** `docker-compose.staging.yml` startet `kr-worker-staging` und nutzt Redis mit Passwortschutz (`--with-scheduler`).
- **Production:** `docker-compose.prod.yml` definiert `worker-1` (mit Scheduler) und `worker-2` (ohne Scheduler) für parallele Verarbeitung.

### Skalierung

- Weitere Worker können in Compose-Dateien dupliziert oder via `docker-compose up --scale worker=N` gestartet werden.
- Nur ein Worker sollte `--with-scheduler` verwenden, um doppelte geplante Jobs zu vermeiden.

### Überwachung

- Logs: `docker-compose logs -f worker` (Dev) bzw. entsprechende Container-Namen in Staging/Production.
- Queue-Statistiken: API Endpoint `/api/v1/scraping/jobs/stats` oder `make worker-stats` lokal.
- Fehlerhafte Jobs verbleiben für 24h (`failure_ttl`) in Redis und können via RQ Dashboard oder CLI analysiert werden.

### Konfiguration

- Worker nutzen die gleichen Environment Variablen wie die API (`DATABASE_URL`, `REDIS_URL`, Secrets Manager Settings).
- Zeitlimits (`RQ_JOB_TIMEOUT`, `RQ_RESULT_TTL`, `RQ_FAILURE_TTL`) sind in `.env` und `Settings` konfigurierbar.

## Health Checks

Health checks operate at multiple layers:

1. **Container Health**: Dockerfile-defined health command.
2. **API Health**: `/health` endpoint for basic readiness.
3. **Detailed Health**: `/health/detailed` to verify dependencies.
4. **Smoke Tests**: Authentication flow, critical endpoints, database, and Redis connectivity.

### Retry-Konfigurationen

Die folgenden Werte werden standardmäßig genutzt:

- Staging: 5 retries × 30s interval (max 2.5 minutes).
- Production: 10 retries × 30s interval (max 5 minutes).
- Any failure triggers automatic rollback.

## Rollback Mechanism

### Automatic Rollback

- Triggered when health checks fail after deployment or smoke tests detect issues.
- Stops new container and restores previous active container.
- Sends critical notification and marks workflow as failed.

### Manual Rollback

- Use `rollback.yml` workflow for post-deployment incidents.
- Requires target version (semantic without `v` prefix).
- Recreates desired state, runs health checks, and logs incident.

**Options:**
- `--restore-db`: Restore latest database backup (use cautiously).
- `--force`: Skip confirmation (automations).
- `--verbose`: Detailed logging.

## Secrets Management

- Development: `.env` files with `SECRETS_MANAGER=none`.
- Staging: Optional `.env.staging` or external secrets provider.
- Production: Recommended AWS Secrets Manager or HashiCorp Vault.

Secrets required for workflows:

- `DEPLOY_SSH_KEY`, `DEPLOY_USER`
- `PRODUCTION_HOST`, `STAGING_HOST`
- `SLACK_WEBHOOK_URL` (optional notifications)
- `SMOKE_TEST_PASSWORD` for auth smoke test
- Optional: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `VAULT_TOKEN`

## Monitoring & Notifications

- **GitHub Actions**: Central log for build/deploy/test stages.
- **Slack/Discord**: Deployment success/failure and rollbacks.
- **Sentry**: Release tracking and incident monitoring.
- **Server Logs**: Located in `/opt/kr-scraper/logs/`.

## Troubleshooting

| Issue | Suggested Actions |
|-------|-------------------|
| SSH connection fails | Verify `DEPLOY_SSH_KEY`, user permissions, and host reachability. |
| Image not found | Confirm build pipeline succeeded and GHCR tag exists. |
| Health checks failing | Execute `./health_check.sh <env> --verbose`, inspect Docker logs, validate database/Redis. |
| Rollback fails | Ensure target version exists, confirm backups, retry with `--verbose`. |
| Secrets missing | Verify secrets manager configuration and logs for "Loaded secrets" entry. |

## Deployment Checklist

### Before Deployment

- [ ] Unit/integration/E2E tests pass locally.
- [ ] Feature validated in staging.
- [ ] CHANGELOG and documentation updated.
- [ ] Team informed of upcoming deployment.

### During Deployment

- [ ] Monitor GitHub Actions logs.
- [ ] Verify `/health` and `/health/detailed` endpoints.
- [ ] Check Sentry for new issues.

### After Deployment

- [ ] Smoke tests complete successfully.
- [ ] Application logs show no critical errors.
- [ ] Notify team of successful deployment.
- [ ] Open follow-up tasks for incidents if necessary.

## Semantic Versioning

- Format: `vMAJOR.MINOR.PATCH` (e.g., `v1.2.3`).
- **MAJOR**: Breaking changes.
- **MINOR**: Backward-compatible feature.
- **PATCH**: Bug fix.

Command reference:

```bash
# Create tag
git tag v1.2.3 -m "Release v1.2.3"

# Push tag
git push origin v1.2.3

# Delete tag if needed
git tag -d v1.2.3
git push origin :refs/tags/v1.2.3
```

## Pipeline Overview

```text
Push to develop → Build → Deploy staging → Health checks → Integration & E2E tests → Notify

Tag push vX.Y.Z → Validate → Build → Scan → Deploy production → Health checks → Smoke tests → Release → Notify

Manual trigger → Validate → Rollback → Health checks → Incident report → Notify
```

## Server Setup Summary

Refer to [`scripts/deployment/README.md`](../scripts/deployment/README.md) for detailed server preparation steps, including Docker installation, directory layout, and SSH configuration.

## FAQ

**Q: How do we deploy a hotfix?**
A: Create a hotfix branch, merge to `main`, tag a patch release (e.g., `v1.2.4`), and push the tag to trigger production deployment.

**Q: Can we skip production deployment automation?**
A: Use manual server scripts only if GitHub Actions is unavailable. Otherwise rely on automated workflows.

**Q: How do we test deployment locally?**
A: Use `docker-compose.staging.yml` to emulate staging locally or deploy to staging environment first.

**Q: What if deployment fails mid-way?**
A: Automatic rollback triggers. Inspect GitHub Actions logs and server health reports, apply fixes, and redeploy.

**Q: How do we roll back to an older version?**
A: Run the `Manual Rollback` workflow with the desired version (e.g., `1.2.1`) and monitor health checks.

**Q: Can multiple deployments run concurrently?**
A: GitHub Actions serializes environment deployments. Wait for current run to finish before triggering another.

**Q: How long do deployments take?**
A: Staging takes ~10-15 minutes; production takes ~20-30 minutes.

## Related Resources

- [`docs/PRODUCTION.md`](PRODUCTION.md)
- [`scripts/deployment/README.md`](../scripts/deployment/README.md)
- [`Makefile`](../Makefile)
- `.github/workflows/deploy.yml`
- `.github/workflows/staging.yml`
- `.github/workflows/rollback.yml`
