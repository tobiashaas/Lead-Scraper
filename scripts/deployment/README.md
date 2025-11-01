# Deployment Scripts Documentation

## Overview

This directory contains deployment automation scripts for KR Lead Scraper. The scripts enable zero-downtime blue-green deployments to production, fast rolling deployments to staging, comprehensive post-deployment health checks, and reliable rollback procedures. They are designed to be invoked by GitHub Actions workflows, but can also be run manually over SSH when necessary.

### Deployment Strategy

- **Production**: Blue-Green deployment to ensure zero downtime and instant rollbacks.
- **Staging**: Rolling deployment for rapid iteration and validation.
- **Automation**: GitHub Actions orchestrates builds, deployments, health checks, and rollbacks.

## Scripts

### `deploy.sh`

- **Purpose**: Executes blue-green deployments on the target server.
- **Usage**: `./deploy.sh <version> <environment>`
  - Example: `./deploy.sh 1.2.3 production`
- **Features**:
  1. Pulls Docker images tagged with semantic versions or staging SHAs.
  2. Starts the inactive (blue/green) container and waits for health.
  3. Runs health checks, database, and Redis connectivity verification.
  4. Swaps traffic to the new container via nginx upstream symlink switching.
  5. Verifies the symlink points to the correct upstream configuration.
  6. Automatically rolls back when failures occur during deployment.
- **Prerequisites**:
  - Docker and Docker Compose installed on the host.
  - `docker-compose.<environment>.yml` and `.env.<environment>` present.
  - SSH user has permissions to manage Docker.
  - Nginx upstream configuration files in `nginx/` directory.

### `health_check.sh`

- **Purpose**: Performs layered health verification after deployments.
- **Usage**: `SMOKE_TEST_PASSWORD='<password>' ./health_check.sh <environment> [--verbose]`
  - Example: `SMOKE_TEST_PASSWORD='secret123' ./health_check.sh production --verbose`
- **Prerequisites**:
  - `jq` must be installed on the server for JSON parsing.
  - `SMOKE_TEST_PASSWORD` environment variable must be set for authentication checks.
- **Checks**:
  - Container health status (Docker).
  - API `/health` endpoint.
  - API `/health/detailed` endpoint (database, Redis, Ollama status).
  - Swagger documentation availability.
  - Database and Redis connectivity via application container.
  - Secrets manager messages in logs.
  - Authentication flow and critical API endpoints (requires `SMOKE_TEST_PASSWORD`).
  - Generates JSON health report in `logs/`.

### `rollback.sh`

- **Purpose**: Automatically roll back to a previous deployment version.
- **Usage**: `./rollback.sh <target_version> <environment> [--restore-db] [--force] [--verbose]`
  - Example: `./rollback.sh 1.2.2 production --force`
- **Features**:
  1. Validates target image availability.
  2. Stops current container and optionally restores database backups.
  3. Starts container with specified version and verifies health.
  4. Generates incident report for auditing and follow-up.
- **Flags**:
  - `--restore-db`: Restore latest database backup (use with caution).
  - `--force`: Skip interactive confirmation (for automation).
  - `--verbose`: Enables command tracing for debugging.

## Blue-Green Traffic Switching

Production deployments use nginx upstream symlink switching for deterministic traffic routing:

1. **Upstream Configuration**: Two files define upstreams pointing to blue and green containers:
   - `nginx/upstream-blue.conf` → `kr-app-prod-blue:8000`
   - `nginx/upstream-green.conf` → `kr-app-prod-green:8000`

2. **Active Symlink**: `nginx/upstream-active.conf` is a symlink pointing to the active upstream file.

3. **Traffic Switch Process**:
   - Deployment script determines target color (blue/green)
   - Updates symlink: `ln -sf upstream-{color}.conf upstream-active.conf`
   - Verifies symlink points to correct file
   - Reloads nginx: `nginx -s reload`

4. **Rollback**: On failure, symlink is switched back to previous upstream and nginx is reloaded.

5. **Verification**: After switch, health endpoint confirms traffic routes to new container.

See `nginx/README.md` for detailed configuration and troubleshooting.

## Deployment Workflow Summary

### Production Deployment

1. Create semantic version tag (`vMAJOR.MINOR.PATCH`).
2. GitHub Actions builds image, pushes to GHCR, and runs security scans.
3. Workflow copies deployment scripts to server and executes `deploy.sh`.
4. Scripts run blue-green deployment, health checks, and upload artifacts.
5. GitHub Release is created with SBOM and vulnerability reports.
6. Slack/Discord notification is sent on success or failure.

### Staging Deployment

1. Push to `develop` branch.
2. GitHub Actions builds staging image (`staging-{sha}`) and deploys via SSH.
3. `deploy.sh` runs in rolling mode for quick updates.
4. `health_check.sh` validates staging environment with relaxed thresholds.
5. Integration and E2E tests run against staging endpoints.
6. Notifications summarize deployment outcome.

### Manual Rollback

1. Trigger `rollback.yml` workflow from GitHub Actions.
2. Provide environment, target version, and reason.
3. Workflow validates target version and executes `rollback.sh`.
4. Health checks verify restored environment.
5. Incident report and notifications are generated automatically.

## Server Preparation

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install jq (required for health checks and JSON parsing)
sudo apt-get update && sudo apt-get install -y jq

# Create deployment directories
sudo mkdir -p /opt/kr-scraper/{logs,backups}
sudo mkdir -p /opt/kr-scraper-staging/{logs,backups}
sudo chown -R deploy:deploy /opt/kr-scraper*

# Set up SSH key for GitHub Actions
ssh-keygen -t ed25519 -C "github-actions@kr-scraper"
# Add public key to ~/.ssh/authorized_keys on target servers
# Add private key to GitHub secrets as DEPLOY_SSH_KEY
```

### Directory Structure

```text
/opt/kr-scraper/
├── docker-compose.prod.yml
├── docker-compose.staging.yml
├── .env.production
├── .env.staging
├── nginx.prod.conf
├── nginx/
│   ├── upstream-blue.conf
│   ├── upstream-green.conf
│   ├── upstream-active.conf (symlink)
│   └── README.md
├── deploy.sh
├── health_check.sh
├── rollback.sh
├── logs/
│   ├── deployment.log
│   ├── health_report_*.json
│   └── rollback.log
└── backups/
    ├── db_backup_*.sql.gz
    ├── env_backup_*
    └── incident_report_*.json
```

## GitHub Secrets

Configure the following secrets under **Settings → Secrets and variables → Actions**:

- `DEPLOY_SSH_KEY`: Private SSH key for deployment user.
- `DEPLOY_USER`: SSH username on target servers (e.g., `deploy`).
- `PRODUCTION_HOST`: Hostname or IP for production server.
- `STAGING_HOST`: Hostname or IP for staging server.
- `SLACK_WEBHOOK_URL`: Webhook for notifications (optional).
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: For AWS Secrets Manager (optional).
- `VAULT_TOKEN`: For HashiCorp Vault (optional).
- `SMOKE_TEST_PASSWORD`: **Required**. Password for `staging_bot` user used in automated authentication health checks. This secret must be passed to `health_check.sh` via environment variable.

Use GitHub **Environments** for environment-specific secrets and approvals.

## Troubleshooting

| Issue | Troubleshooting Steps |
|-------|----------------------|
| Docker image not found | Ensure build workflow succeeded and image tag exists in GHCR. |
| SSH connection failure | Verify `DEPLOY_SSH_KEY`, host accessibility, and SSH permissions. |
| Health checks failing | Run `./health_check.sh <env> --verbose`, inspect container logs, validate database/Redis connectivity. |
| Rollback failure | Confirm target tag exists, ensure backups are present, re-run with `--verbose` and check incident report. |
| Secrets not loading | Confirm secrets manager configuration and look for "Loaded secrets from" in container logs. |

## Best Practices

1. Always deploy to staging before production.
2. Maintain semantic versioning for production releases.
3. Monitor GitHub Actions logs during deployments.
4. Keep backups for at least 30 days.
5. Regularly test rollback procedure in staging.
6. Use automated health checks and smoke tests to validate deployments.
7. Document incidents and follow-up actions for every rollback.
8. Automate notifications to ensure rapid response to failures.

## Related Documentation

- [`docs/DEPLOYMENT.md`](../../docs/DEPLOYMENT.md) – complete deployment guide.
- [`docs/PRODUCTION.md`](../../docs/PRODUCTION.md) – production environment reference.
- [`Makefile`](../../Makefile) – includes deployment commands for local developers.
