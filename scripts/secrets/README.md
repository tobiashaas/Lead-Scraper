# Secrets Management Tooling

This directory provides setup and rotation tooling for managing secrets in KR Lead Scraper. The scripts integrate with `app/core/secrets_manager.py` and support both AWS Secrets Manager and HashiCorp Vault providers.

## Prerequisites

- Python 3.11+ (to run rotation CLI)
- `boto3`, `hvac`, and `cryptography` installed (from `requirements.txt`)
- AWS CLI configured (for AWS setup script)
- HashiCorp Vault CLI installed and authenticated (for Vault setup script)
- `BACKUP_ENCRYPTION_KEY` environment variable for encrypted backups (Fernet key)

## Initial Setup

### AWS Secrets Manager

```bash
./scripts/secrets/setup_aws_secrets.sh --secret-name kr-scraper/production --region eu-central-1 --create-policy
```

- Generates strong random values for core credentials.
- Leaves optional integration keys blank for later update.
- Validates the stored JSON payload.
- Optionally creates a minimal IAM policy granting `secretsmanager:GetSecretValue` and `DescribeSecret`.

### HashiCorp Vault

```bash
./scripts/secrets/setup_vault_secrets.sh --vault-addr https://vault.example.com --vault-path secret/data/kr-scraper
```

- Ensures KV v2 is enabled at `secret/`.
- Stores initial secret payload with random credentials.
- Creates a read/list policy and issues a short-lived application token (displayed once).

## Rotation

Use the Python CLI to rotate sensitive credentials while preserving non-critical fields:

```bash
python scripts/secrets/rotate_secrets.py --provider aws --secret-name kr-scraper/production --region eu-central-1 --backup
```

Common flags:

- `--backup`: Encrypt current payload to `scripts/secrets/backups/` using `BACKUP_ENCRYPTION_KEY`.
- `--dry-run`: Preview rotation without writing to the provider.
- `--rollback <file>`: Restore secrets from a previous encrypted backup.
- `--verbose`: Enable debug-level logging (masked).

Supported providers:

- `--provider aws`: Requires `--secret-name` and `--region` (or `AWS_REGION`).
- `--provider vault`: Requires `--vault-addr`, `--vault-token`, `--vault-path` (or respective env vars).

## Backups & Rollback

Backups are encrypted with Fernet using `BACKUP_ENCRYPTION_KEY`. Store the key securely and rotate it periodically.

Rollback example:

```bash
python scripts/secrets/rotate_secrets.py --provider vault --rollback scripts/secrets/backups/secrets_backup_20251029_120000.json.enc --vault-addr https://vault.example.com --vault-token $VAULT_TOKEN --vault-path secret/data/kr-scraper
```

## Automation

- Integrate rotation CLI with cron/systemd timers for regular (e.g., 90-day) rotations.
- For AWS deployments using EC2/ECS, rely on instance/task roles rather than static credentials.
- For Vault, prefer short-lived application tokens with renewal.

## Troubleshooting

- Ensure provider SDK dependencies are installed (`boto3`, `hvac`).
- Verify network access to AWS/Vault endpoints.
- Check `BACKUP_ENCRYPTION_KEY` is set before using backup/rollback.
- Use `--verbose` for additional masked logging.

Refer to `docs/PRODUCTION.md#secrets-management` for end-to-end operational guidance.
