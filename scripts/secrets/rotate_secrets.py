#!/usr/bin/env python3
"""Secrets rotation utility for KR Lead Scraper.

Supports AWS Secrets Manager and HashiCorp Vault using the existing provider
abstractions. Provides optional encrypted backups and rollback capability.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import secrets as secrets_module
import string


LOGGER = logging.getLogger("scripts.secrets.rotate")
MASK = "******"
SCRIPT_DIR = Path(__file__).resolve().parent
BACKUP_DIR = SCRIPT_DIR / "backups"
BACKUP_KEY_ENV = "BACKUP_ENCRYPTION_KEY"


class RotationError(RuntimeError):
    """Raised when rotation or rollback fails."""


@dataclass(slots=True)
class ProviderOptions:
    provider: str
    secret_name: str | None = None
    region: str | None = None
    vault_addr: str | None = None
    vault_token: str | None = None
    vault_path: str | None = None
    dry_run: bool = False


@dataclass(slots=True)
class RotationContext:
    provider_options: ProviderOptions
    backup: bool
    rollback_path: Path | None
    verbose: bool


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rotate or roll back secrets for KR Lead Scraper",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--provider",
        required=True,
        choices=("aws", "vault"),
        help="Secrets manager provider to use",
    )
    parser.add_argument("--secret-name", help="Secret name/ARN for AWS Secrets Manager")
    parser.add_argument("--region", help="AWS region for the secret")
    parser.add_argument("--vault-addr", help="Vault server address (e.g. https://vault.example.com)")
    parser.add_argument("--vault-token", help="Vault token with read/write permissions")
    parser.add_argument("--vault-path", help="Full Vault KV v2 path, e.g. secret/data/kr-scraper")

    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create an encrypted backup of the current secrets before rotation",
    )
    parser.add_argument(
        "--rollback",
        metavar="FILE",
        help="Rollback using the given encrypted backup file (implies no rotation)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show actions without writing to the provider",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")


def mask_value(_: str) -> str:
    return MASK


def masked_items(data: dict[str, Any], mask_func: Callable[[str], str] | None = None) -> dict[str, Any]:
    mask = mask_func or mask_value
    return {key: (mask(key) if data.get(key) else "<unset>") for key in data}


# ---------------------------------------------------------------------------
# Secret generation utilities
# ---------------------------------------------------------------------------

def generate_secret_key() -> str:
    return secrets_module.token_urlsafe(32)


def _generate_password(length: int) -> str:
    alphabet = string.ascii_letters + string.digits + string.punctuation
    while True:
        password = "".join(secrets_module.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in string.punctuation for c in password)
        ):
            return password


def generate_password(length: int = 32) -> str:
    return _generate_password(length)


# ---------------------------------------------------------------------------
# Provider operations
# ---------------------------------------------------------------------------

def load_current_secrets(options: ProviderOptions) -> dict[str, Any]:
    if options.provider == "aws":
        return _load_aws_secret(options)
    return _load_vault_secret(options)


def _load_aws_secret(options: ProviderOptions) -> dict[str, Any]:
    if not options.secret_name or not options.region:
        raise RotationError("AWS provider requires --secret-name and --region")

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency missing
        raise RotationError("boto3 is required for AWS secrets rotation") from exc

    client = boto3.client("secretsmanager", region_name=options.region)
    try:
        response = client.get_secret_value(SecretId=options.secret_name)
    except (ClientError, BotoCoreError) as exc:
        raise RotationError(f"Failed to load AWS secret '{options.secret_name}': {exc}") from exc

    secret_string = response.get("SecretString")
    if secret_string:
        try:
            return json.loads(secret_string)
        except json.JSONDecodeError as exc:
            raise RotationError("AWS secret is not valid JSON") from exc

    if response.get("SecretBinary"):
        raise RotationError("Binary secrets are not supported for rotation")

    return {}


def _load_vault_secret(options: ProviderOptions) -> dict[str, Any]:
    if not options.vault_addr or not options.vault_token or not options.vault_path:
        raise RotationError("Vault provider requires --vault-addr, --vault-token, and --vault-path")

    try:
        import hvac
        from hvac.exceptions import VaultError
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency missing
        raise RotationError("hvac is required for Vault secrets rotation") from exc

    client = hvac.Client(url=options.vault_addr, token=options.vault_token)
    try:
        response = client.secrets.kv.v2.read_secret_version(path=options.vault_path)
    except VaultError as exc:
        raise RotationError(f"Failed to load Vault secret '{options.vault_path}': {exc}") from exc

    data = response.get("data", {}).get("data")
    if data is None:
        return {}

    if not isinstance(data, dict):
        raise RotationError("Vault secret payload is not a dict")

    return data


# ---------------------------------------------------------------------------
# Backups & rollback
# ---------------------------------------------------------------------------

def get_fernet() -> "Fernet":
    try:
        from cryptography.fernet import Fernet
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency missing
        raise RotationError("cryptography is required for encrypted backups") from exc

    key = os.getenv(BACKUP_KEY_ENV)
    if not key:
        raise RotationError(f"Environment variable {BACKUP_KEY_ENV} is required for backups")

    try:
        return Fernet(key.encode() if not isinstance(key, bytes) else key)
    except Exception as exc:  # noqa: BLE001
        raise RotationError("Invalid Fernet key provided") from exc


def create_backup(payload: dict[str, Any]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"secrets_backup_{timestamp}.json.enc"

    fernet = get_fernet()
    encrypted = fernet.encrypt(json.dumps(payload).encode("utf-8"))
    backup_path.write_bytes(encrypted)

    LOGGER.info("Encrypted backup written to %s", backup_path)
    return backup_path


def load_backup(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RotationError(f"Backup file not found: {path}")

    fernet = get_fernet()
    try:
        decrypted = fernet.decrypt(path.read_bytes())
    except Exception as exc:  # noqa: BLE001
        raise RotationError("Failed to decrypt backup file") from exc

    try:
        payload = json.loads(decrypted.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RotationError("Backup file payload is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise RotationError("Backup file does not contain a JSON object")

    return payload


# ---------------------------------------------------------------------------
# Rotation logic
# ---------------------------------------------------------------------------

CRITICAL_KEYS = {
    "SECRET_KEY": generate_secret_key,
    "POSTGRES_PASSWORD": lambda: generate_password(32),
    "REDIS_PASSWORD": lambda: generate_password(32),
    "TOR_CONTROL_PASSWORD": lambda: generate_password(24),
}


SENSITIVE_KEYS = {
    "SECRET_KEY",
    "POSTGRES_PASSWORD",
    "REDIS_PASSWORD",
    "TOR_CONTROL_PASSWORD",
    "GOOGLE_PLACES_API_KEY",
    "TWOCAPTCHA_API_KEY",
    "SENTRY_DSN",
}


def rotate_payload(existing: dict[str, Any]) -> dict[str, Any]:
    payload = dict(existing)
    rotated_keys: list[str] = []

    for key, generator in CRITICAL_KEYS.items():
        new_value = generator()
        if payload.get(key):
            if payload[key] != new_value:
                payload[key] = new_value
                rotated_keys.append(key)
        else:
            payload[key] = new_value
            rotated_keys.append(key)

    if rotated_keys:
        LOGGER.info("Rotated keys: %s", ", ".join(rotated_keys))
    else:
        LOGGER.info("No keys required rotation")

    return payload


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def write_secrets(options: ProviderOptions, payload: dict[str, Any]) -> None:
    if options.provider == "aws":
        _write_aws_secret(options, payload)
    else:
        _write_vault_secret(options, payload)


def _write_aws_secret(options: ProviderOptions, payload: dict[str, Any]) -> None:
    if not options.secret_name or not options.region:
        raise RotationError("AWS provider requires --secret-name and --region")

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency missing
        raise RotationError("boto3 is required for AWS secrets rotation") from exc

    client = boto3.client("secretsmanager", region_name=options.region)
    try:
        client.update_secret(SecretId=options.secret_name, SecretString=json.dumps(payload))
    except (ClientError, BotoCoreError) as exc:
        raise RotationError(f"Failed to update AWS secret '{options.secret_name}': {exc}") from exc

    LOGGER.info("AWS secret '%s' updated", options.secret_name)


def _write_vault_secret(options: ProviderOptions, payload: dict[str, Any]) -> None:
    if not options.vault_addr or not options.vault_token or not options.vault_path:
        raise RotationError("Vault provider requires --vault-addr, --vault-token, and --vault-path")

    try:
        import hvac
        from hvac.exceptions import VaultError
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency missing
        raise RotationError("hvac is required for Vault secrets rotation") from exc

    client = hvac.Client(url=options.vault_addr, token=options.vault_token)
    try:
        client.secrets.kv.v2.create_or_update_secret(path=options.vault_path, secret=payload)
    except VaultError as exc:
        raise RotationError(f"Failed to update Vault secret '{options.vault_path}': {exc}") from exc

    LOGGER.info("Vault secret '%s' updated", options.vault_path)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def validate_inputs(args: argparse.Namespace) -> ProviderOptions:
    provider = args.provider.lower()
    options = ProviderOptions(
        provider=provider,
        secret_name=args.secret_name,
        region=args.region,
        vault_addr=args.vault_addr,
        vault_token=args.vault_token,
        vault_path=args.vault_path,
        dry_run=args.dry_run,
    )

    if provider == "aws":
        if not options.secret_name:
            raise RotationError("--secret-name is required for AWS provider")
        options.region = options.region or os.getenv("AWS_REGION")
        if not options.region:
            raise RotationError("AWS region must be provided via --region or AWS_REGION env var")
    elif provider == "vault":
        options.vault_addr = options.vault_addr or os.getenv("VAULT_ADDR")
        options.vault_token = options.vault_token or os.getenv("VAULT_TOKEN")
        options.vault_path = options.vault_path or os.getenv("VAULT_PATH")
        missing = [
            name
            for name, value in (
                ("--vault-addr", options.vault_addr),
                ("--vault-token", options.vault_token),
                ("--vault-path", options.vault_path),
            )
            if not value
        ]
        if missing:
            raise RotationError("Vault provider requires: " + ", ".join(missing))
    else:  # pragma: no cover - argparse already restricts choices
        raise RotationError(f"Unsupported provider: {provider}")

    return options


def run_rotation(context: RotationContext) -> None:
    options = context.provider_options

    if context.rollback_path:
        payload = load_backup(context.rollback_path)
        LOGGER.info("Loaded payload from backup for rollback")
    else:
        current_secrets = load_current_secrets(options)
        LOGGER.info(
            "Loaded current secrets metadata: %s",
            masked_items({key: current_secrets.get(key, "") for key in SENSITIVE_KEYS}),
        )

        if context.backup:
            backup_path = create_backup(current_secrets)
            LOGGER.info("Backup created at %s", backup_path)

        payload = rotate_payload(current_secrets)

    if options.dry_run:
        LOGGER.info("Dry run enabled; secrets not persisted")
        LOGGER.debug("Payload snapshot (masked): %s", masked_items(payload))
        return

    write_secrets(options, payload)
    LOGGER.info("Secrets %s completed", "rollback" if context.rollback_path else "rotation")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        options = validate_inputs(args)
        context = RotationContext(
            provider_options=options,
            backup=bool(args.backup),
            rollback_path=Path(args.rollback) if args.rollback else None,
            verbose=bool(args.verbose),
        )
        configure_logging(context.verbose)
        run_rotation(context)
        return 0
    except RotationError as exc:
        configure_logging(args.verbose)
        LOGGER.error("%s", exc)
        return 1
    except Exception as exc:  # noqa: BLE001 - defensive
        configure_logging(args.verbose)
        LOGGER.exception("Unexpected error during secrets rotation: %s", exc)
        return 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
