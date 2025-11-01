"""Secrets management abstraction layer.

Provides provider-independent access to secrets with caching and graceful
fallback capabilities. Supports AWS Secrets Manager and HashiCorp Vault.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from cachetools import TTLCache

logger = logging.getLogger(__name__)


class SecretsProvider(ABC):
    """Abstract base class for secrets providers."""

    def __init__(self, cache_ttl: int = 300, cache_maxsize: int = 128) -> None:
        self._cache_ttl = cache_ttl
        self._cache_maxsize = cache_maxsize
        self._cache = TTLCache(maxsize=self._cache_maxsize, ttl=self._cache_ttl)
        self._cache_lock = threading.Lock()

    @abstractmethod
    def get_secret(self, secret_name: str) -> dict[str, Any]:
        """Retrieve a secret from the underlying provider."""

    @abstractmethod
    def update_secret(self, secret_name: str, secret_value: dict[str, Any]) -> bool:
        """Update or rotate a secret value."""

    @abstractmethod
    def list_secrets(self) -> list[str]:
        """List available secret identifiers."""

    def invalidate_cache(self, secret_name: str | None = None) -> None:
        """Invalidate cached entries."""

        with self._cache_lock:
            if secret_name is None:
                self._cache.clear()
            else:
                self._cache.pop(secret_name, None)

    def get_secret_cached(self, secret_name: str, ttl: int | None = None) -> dict[str, Any]:
        """Get secret with TTL-based caching."""

        with self._cache_lock:
            if ttl and ttl != self._cache.ttl:
                self._cache = TTLCache(maxsize=self._cache_maxsize, ttl=ttl)

            try:
                return self._cache[secret_name]
            except KeyError:
                secret = self.get_secret(secret_name)
                self._cache[secret_name] = secret
                return secret


class AWSSecretsProvider(SecretsProvider):
    """Secrets provider backed by AWS Secrets Manager."""

    def __init__(
        self,
        region_name: str,
        profile_name: str | None = None,
        cache_ttl: int = 300,
    ) -> None:
        super().__init__(cache_ttl=cache_ttl)

        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError
        except ModuleNotFoundError as exc:  # pragma: no cover - defensive guard
            raise RuntimeError(
                "boto3 is required for AWS secrets provider. Install boto3 to use this feature."
            ) from exc

        self._boto3 = boto3
        self._client_error = ClientError
        self._boto_error = BotoCoreError

        session_kwargs: dict[str, Any] = {"region_name": region_name}
        if profile_name:
            session_kwargs["profile_name"] = profile_name

        session = self._boto3.session.Session(**session_kwargs)
        self._client = session.client("secretsmanager")

    def get_secret(self, secret_name: str) -> dict[str, Any]:
        try:
            response = self._client.get_secret_value(SecretId=secret_name)
        except self._client_error as err:
            logger.warning(
                "Failed to fetch secret '%s' from AWS Secrets Manager: %s", secret_name, err
            )
            return {}
        except self._boto_error as err:  # pragma: no cover - network issues
            logger.warning("AWS BotoCore error while fetching secret '%s': %s", secret_name, err)
            return {}

        secret_string = response.get("SecretString")
        if secret_string:
            try:
                return json.loads(secret_string)
            except json.JSONDecodeError:
                logger.error("Secret '%s' is not valid JSON", secret_name)
                return {}

        secret_binary = response.get("SecretBinary")
        if secret_binary:  # pragma: no cover - binary secrets not expected but handled
            try:
                decoded = secret_binary.decode("utf-8")
                return json.loads(decoded)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to decode binary secret '%s': %s", secret_name, exc)
                return {}

        logger.info("Secret '%s' is empty in AWS Secrets Manager", secret_name)
        return {}

    def update_secret(self, secret_name: str, secret_value: dict[str, Any]) -> bool:
        try:
            self._client.update_secret(
                SecretId=secret_name,
                SecretString=json.dumps(secret_value),
            )
        except self._client_error as err:
            logger.error(
                "Failed to update secret '%s' in AWS Secrets Manager: %s", secret_name, err
            )
            return False
        except self._boto_error as err:  # pragma: no cover - network issues
            logger.error("AWS BotoCore error while updating secret '%s': %s", secret_name, err)
            return False

        self.invalidate_cache(secret_name)
        return True

    def list_secrets(self) -> list[str]:
        try:
            paginator = self._client.get_paginator("list_secrets")
            secret_names: list[str] = []
            for page in paginator.paginate():
                for secret in page.get("SecretList", []):
                    name = secret.get("Name")
                    if name:
                        secret_names.append(name)
            return secret_names
        except Exception as err:  # noqa: BLE001 - boto-specific errors
            logger.warning("Failed to list AWS secrets: %s", err)
            return []


class VaultSecretsProvider(SecretsProvider):
    """Secrets provider backed by HashiCorp Vault."""

    def __init__(
        self,
        vault_addr: str,
        vault_token: str,
        vault_path: str = "secret/data/kr-scraper",
        cache_ttl: int = 300,
    ) -> None:
        super().__init__(cache_ttl=cache_ttl)

        try:
            import hvac
            from hvac.exceptions import InvalidPath, VaultError
        except ModuleNotFoundError as exc:  # pragma: no cover - defensive guard
            raise RuntimeError(
                "hvac is required for Vault secrets provider. Install hvac to use this feature."
            ) from exc

        self._hvac = hvac
        self._vault_error = VaultError
        self._invalid_path = InvalidPath

        self._client = self._hvac.Client(url=vault_addr, token=vault_token)
        self._vault_path = vault_path

    def get_secret(self, secret_name: str) -> dict[str, Any]:
        path = self._resolve_path(secret_name)
        try:
            response = self._client.secrets.kv.v2.read_secret_version(path=path)
        except self._invalid_path:
            logger.warning("Vault secret path '%s' not found", path)
            return {}
        except self._vault_error as err:
            logger.warning("Failed to fetch secret '%s' from Vault: %s", path, err)
            return {}

        data = response.get("data", {}).get("data")
        if isinstance(data, dict):
            return data

        logger.info("Vault secret '%s' has no data", path)
        return {}

    def update_secret(self, secret_name: str, secret_value: dict[str, Any]) -> bool:
        path = self._resolve_path(secret_name)
        try:
            self._client.secrets.kv.v2.create_or_update_secret(path=path, secret=secret_value)
        except self._vault_error as err:
            logger.error("Failed to update secret '%s' in Vault: %s", path, err)
            return False

        self.invalidate_cache(secret_name)
        return True

    def list_secrets(self) -> list[str]:
        base_path = self._vault_path.rstrip("/")
        try:
            response = self._client.secrets.kv.v2.list_secrets(path=base_path)
        except self._invalid_path:
            logger.warning("Vault path '%s' not found while listing secrets", base_path)
            return []
        except self._vault_error as err:
            logger.warning("Failed to list Vault secrets: %s", err)
            return []

        keys = response.get("data", {}).get("keys", [])
        return [self._resolve_path(key) for key in keys if isinstance(key, str)]

    def _resolve_path(self, secret_name: str) -> str:
        if secret_name.startswith("secret/"):
            return secret_name
        base = self._vault_path.rstrip("/")
        return f"{base}/{secret_name}" if secret_name else base


@dataclass(slots=True)
class ProviderConfig:
    provider_type: str
    aws_region: str = "eu-central-1"
    aws_profile: str | None = None
    aws_secret_name: str = ""
    vault_addr: str = ""
    vault_token: str = ""
    vault_path: str = "secret/data/kr-scraper"


def get_secrets_provider(
    provider_type: str, config: ProviderConfig | None = None
) -> SecretsProvider | None:
    """Factory returning a secrets provider instance."""

    provider = (provider_type or "none").lower().strip()

    if provider == "none":
        logger.info("Secrets manager disabled; using environment variables.")
        return None

    config = config or ProviderConfig(provider_type=provider)

    if provider == "aws":
        if not config.aws_region:
            logger.warning("AWS region not configured; falling back to environment variables.")
            return None

        try:
            return AWSSecretsProvider(
                region_name=config.aws_region,
                profile_name=config.aws_profile,
            )
        except RuntimeError as exc:
            logger.warning("AWS provider unavailable: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to initialize AWS secrets provider: %s", exc)
        return None

    if provider == "vault":
        if not config.vault_addr or not config.vault_token:
            logger.warning("Vault configuration incomplete; falling back to environment variables.")
            return None

        try:
            return VaultSecretsProvider(
                vault_addr=config.vault_addr,
                vault_token=config.vault_token,
                vault_path=config.vault_path or "secret/data/kr-scraper",
            )
        except RuntimeError as exc:
            logger.warning("Vault provider unavailable: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to initialize Vault secrets provider: %s", exc)
        return None

    logger.warning(
        "Unknown secrets manager provider '%s'; falling back to environment variables.",
        provider_type,
    )
    return None


def load_secrets_from_manager(
    secret_name: str,
    provider: SecretsProvider | None,
    ttl: int = 300,
) -> dict[str, Any]:
    """Load secrets from the configured provider if available."""

    if provider is None:
        logger.debug("Secrets provider not configured; using environment variables only.")
        return {}

    try:
        secrets = provider.get_secret_cached(secret_name, ttl=ttl)
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.warning("Failed to load secret '%s' from provider: %s", secret_name, exc)
        return {}

    if secrets:
        logger.info("Loaded secrets for '%s' from provider.", secret_name)
    else:
        logger.warning(
            "Secret '%s' not found in provider; falling back to environment variables.", secret_name
        )

    return secrets


def build_provider_config_from_env() -> ProviderConfig:
    """Build provider configuration from environment variables."""

    return ProviderConfig(
        provider_type=os.getenv("SECRETS_MANAGER", "none"),
        aws_region=os.getenv("AWS_REGION", "eu-central-1"),
        aws_profile=os.getenv("AWS_PROFILE"),
        aws_secret_name=os.getenv("AWS_SECRETS_NAME", ""),
        vault_addr=os.getenv("VAULT_ADDR", ""),
        vault_token=os.getenv("VAULT_TOKEN", ""),
        vault_path=os.getenv("VAULT_PATH", "secret/data/kr-scraper"),
    )
