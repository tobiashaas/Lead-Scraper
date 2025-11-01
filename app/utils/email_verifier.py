"""Email verification utilities with SMTP, optional API integrations, and caching."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Tuple

import dns.exception
import dns.resolver
import httpx
import redis.asyncio as redis
from aiosmtplib import SMTP, SMTPException

from app.core.config import settings


logger = logging.getLogger(__name__)


EMAIL_CACHE_PREFIX = "email_verification:"
MX_CACHE_PREFIX = "email_verification_mx:"
RATE_LIMIT_PREFIX = "email_verification_rate:"
RATE_LIMIT_WINDOW_SECONDS = 60


class EmailVerificationError(Exception):
    """Base exception for email verification errors."""


class EmailVerificationRateLimited(EmailVerificationError):
    """Raised when verification rate limit is exceeded."""


@dataclass(slots=True)
class EmailVerificationResult:
    """Structured result for email verification operations."""

    valid: bool
    status: str
    method: str
    message: str | None = None
    provider: str | None = None
    deliverable: bool | None = None
    cached: bool = False
    verified_at: datetime | None = None

    def to_json(self) -> str:
        payload = {
            "valid": self.valid,
            "status": self.status,
            "method": self.method,
            "message": self.message,
            "provider": self.provider,
            "deliverable": self.deliverable,
            "cached": self.cached,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
        }
        return json.dumps(payload)

    @classmethod
    def from_serialized(cls, payload: str) -> "EmailVerificationResult":
        data = json.loads(payload)
        verified_at = (
            datetime.fromisoformat(data["verified_at"]).astimezone(timezone.utc)
            if data.get("verified_at")
            else None
        )
        return cls(
            valid=data.get("valid", False),
            status=data.get("status", "unknown"),
            method=data.get("method", "smtp"),
            message=data.get("message"),
            provider=data.get("provider"),
            deliverable=data.get("deliverable"),
            cached=data.get("cached", False),
            verified_at=verified_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "status": self.status,
            "method": self.method,
            "message": self.message,
            "provider": self.provider,
            "deliverable": self.deliverable,
            "cached": self.cached,
            "verified_at": self.verified_at,
        }


class EmailVerifier:
    """Email verification service supporting SMTP and optional API providers."""

    def __init__(
        self,
        use_api: bool | None = None,
        api_provider: str | None = None,
        api_key: str | None = None,
    ) -> None:
        method = (settings.email_verification_method or "smtp").lower()
        if use_api is None:
            use_api = method in {"api", "both"}

        self.use_api = use_api
        self.api_provider = (api_provider or settings.email_verification_api_provider or "").lower()
        self.api_key = api_key or settings.email_verification_api_key

        self.smtp_timeout = settings.email_verification_smtp_timeout
        self.cache_ttl = settings.email_verification_cache_ttl
        self.rate_limit_per_minute = settings.email_verification_rate_limit
        self.mail_from = "noreply@lead-scraper.local"
        self.method_preference = method
        self.max_concurrent = settings.verification_max_concurrent

        self._redis: redis.Redis | None = None
        self._redis_lock = asyncio.Lock()

    async def _get_redis(self) -> redis.Redis | None:
        if self._redis:
            return self._redis

        async with self._redis_lock:
            if self._redis:
                return self._redis

            try:
                client = redis.from_url(
                    settings.redis_url,
                    db=settings.redis_db,
                    decode_responses=True,
                    encoding="utf-8",
                )
                await client.ping()
                self._redis = client
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("EmailVerifier: Redis connection unavailable: %s", exc)
                self._redis = None
        return self._redis

    async def close(self) -> None:
        if self._redis:
            try:
                await self._redis.close()
            except Exception:  # pragma: no cover - best effort
                logger.debug("EmailVerifier: failed to close redis", exc_info=True)
            finally:
                self._redis = None

    async def get_mx_records(self, domain: str) -> list[tuple[int, str]]:
        cache_key = f"{MX_CACHE_PREFIX}{domain}"
        redis_client = await self._get_redis()

        if redis_client:
            cached = await redis_client.get(cache_key)
            if cached:
                try:
                    records = json.loads(cached)
                    return [(int(priority), host) for priority, host in records]
                except (TypeError, ValueError):
                    logger.debug("EmailVerifier: invalid MX cache for domain %s", domain)

        try:
            answers = await asyncio.to_thread(dns.resolver.resolve, domain, "MX")
            mx_records = sorted(
                ((r.preference, str(r.exchange).rstrip(".")) for r in answers),
                key=lambda item: item[0],
            )
        except dns.resolver.NXDOMAIN:
            logger.info("EmailVerifier: no MX records for domain %s", domain)
            mx_records = []
        except (dns.resolver.NoAnswer, dns.exception.DNSException) as exc:
            logger.warning("EmailVerifier: DNS lookup failed for %s: %s", domain, exc)
            mx_records = []

        if redis_client and mx_records:
            await redis_client.setex(cache_key, 86400, json.dumps(mx_records))

        return mx_records

    async def _record_rate_limit(self, domain: str) -> None:
        if not self.rate_limit_per_minute:
            return

        redis_client = await self._get_redis()
        if not redis_client:
            return

        key = f"{RATE_LIMIT_PREFIX}{domain.lower()}"
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW_SECONDS

        await redis_client.zremrangebyscore(key, 0, window_start)
        await redis_client.zadd(key, {str(now): now})
        await redis_client.expire(key, RATE_LIMIT_WINDOW_SECONDS * 2)

    async def _enforce_rate_limit(self, domain: str) -> None:
        if not self.rate_limit_per_minute:
            return

        redis_client = await self._get_redis()
        if not redis_client:
            return

        key = f"{RATE_LIMIT_PREFIX}{domain.lower()}"
        window_start = time.time() - RATE_LIMIT_WINDOW_SECONDS

        for _ in range(RATE_LIMIT_WINDOW_SECONDS):
            await redis_client.zremrangebyscore(key, 0, window_start)
            count = await redis_client.zcard(key)
            if count < self.rate_limit_per_minute:
                return
            await asyncio.sleep(1)

        raise EmailVerificationRateLimited(f"Rate limit exceeded for domain {domain}")

    @asynccontextmanager
    async def _smtp_client(self, hostname: str):
        client = SMTP(hostname=hostname, port=25, timeout=self.smtp_timeout)
        try:
            await client.connect()
            await client.ehlo()
            yield client
        finally:
            try:
                await client.quit()
            except SMTPException:  # pragma: no cover - depends on server responses
                logger.debug("EmailVerifier: failed to quit SMTP cleanly", exc_info=True)

    async def verify_email_smtp(self, email: str) -> EmailVerificationResult:
        local_part, _, domain = email.partition("@")
        if not domain or not local_part:
            return EmailVerificationResult(
                valid=False,
                status="invalid_format",
                method="smtp",
                message="Email address missing local part or domain.",
            )

        try:
            await self._enforce_rate_limit(domain)
        except EmailVerificationRateLimited:
            return EmailVerificationResult(
                valid=False,
                status="rate_limited",
                method="smtp",
                message="Domain verification rate limit exceeded.",
            )

        mx_records = await self.get_mx_records(domain)
        if not mx_records:
            return EmailVerificationResult(
                valid=False,
                status="no_mx_records",
                method="smtp",
                message="No MX records found for domain.",
            )

        status = "unknown"
        message: str | None = None

        for _, mx_host in mx_records:
            try:
                async with self._smtp_client(mx_host) as client:
                    await client.mail(self.mail_from)
                    code, response = await client.rcpt(email)
                    await self._record_rate_limit(domain)

                response_message = response.decode() if isinstance(response, bytes) else str(response)
                message = response_message

                if code == 250:
                    return EmailVerificationResult(
                        valid=True,
                        status="valid",
                        method="smtp",
                        message=response_message,
                    )
                if code in {451, 452}:
                    status = "temporary_error"
                    message = response_message
                elif code == 550:
                    status = "invalid"
                    message = response_message
                else:
                    status = f"smtp_{code}"
                    message = response_message

            except SMTPException as exc:
                logger.debug("EmailVerifier: SMTP error for %s via %s: %s", email, mx_host, exc)
                status = "smtp_error"
                message = str(exc)
            except Exception as exc:  # pragma: no cover - safety
                logger.debug("EmailVerifier: unexpected error verifying %s: %s", email, exc)
                status = "smtp_error"
                message = str(exc)

        return EmailVerificationResult(
            valid=status == "valid",
            status=status,
            method="smtp",
            message=message,
        )

    async def verify_email_api(self, email: str, provider: str | None = None) -> EmailVerificationResult:
        provider_to_use = (provider or self.api_provider or "").lower()
        if not provider_to_use:
            return EmailVerificationResult(
                valid=False,
                status="api_not_configured",
                method="api",
                message="No API provider configured.",
            )

        if not self.api_key:
            return EmailVerificationResult(
                valid=False,
                status="api_missing_key",
                method="api",
                provider=provider_to_use,
                message="API key missing for email verification provider.",
            )

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                if provider_to_use == "zerobounce":
                    response = await client.get(
                        "https://api.zerobounce.net/v2/validate",
                        params={"api_key": self.api_key, "email": email},
                    )
                    payload = response.json()
                    status = payload.get("status", "unknown").lower()
                    valid = status in {"valid", "catch-all"}
                    deliverable = payload.get("status", "").lower() == "valid"
                    return EmailVerificationResult(
                        valid=valid,
                        status=status or "unknown",
                        method="api",
                        provider=provider_to_use,
                        deliverable=deliverable,
                        message=payload.get("sub_status"),
                    )

                if provider_to_use == "hunter":
                    response = await client.get(
                        "https://api.hunter.io/v2/email-verifier",
                        params={"api_key": self.api_key, "email": email},
                    )
                    data = response.json().get("data", {})
                    result = data.get("result", "unknown").lower()
                    status = result or "unknown"
                    return EmailVerificationResult(
                        valid=status in {"deliverable", "risky"},
                        status=status,
                        method="api",
                        provider=provider_to_use,
                        deliverable=status == "deliverable",
                        message=data.get("score"),
                    )

                if provider_to_use == "emaillistverify":
                    response = await client.get(
                        "https://apps.emaillistverify.com/api/verifEmail",
                        params={"secret": self.api_key, "email": email},
                    )
                    result_text = response.text.strip().lower()
                    deliverable = result_text == "ok"
                    status = "valid" if deliverable else result_text or "unknown"
                    return EmailVerificationResult(
                        valid=deliverable,
                        status=status,
                        method="api",
                        provider=provider_to_use,
                        deliverable=deliverable,
                        message=result_text,
                    )

                return EmailVerificationResult(
                    valid=False,
                    status="api_unsupported",
                    method="api",
                    provider=provider_to_use,
                    message="Unsupported email verification provider.",
                )
        except httpx.HTTPError as exc:
            logger.warning("EmailVerifier: API request failed for %s: %s", email, exc)
            return EmailVerificationResult(
                valid=False,
                status="api_error",
                method="api",
                provider=provider_to_use,
                message=str(exc),
            )

    async def verify_email(self, email: str, use_cache: bool = True) -> EmailVerificationResult:
        normalized_email = email.strip().lower()
        redis_client = await self._get_redis()
        cache_key = f"{EMAIL_CACHE_PREFIX}{normalized_email}"

        if use_cache and redis_client:
            cached = await redis_client.get(cache_key)
            if cached:
                result = EmailVerificationResult.from_serialized(cached)
                result.cached = True
                return result

        verification_result: EmailVerificationResult | None = None

        if self.use_api and self.method_preference in {"api", "both"}:
            verification_result = await self.verify_email_api(normalized_email)
            if verification_result.status in {"api_error", "api_missing_key", "api_not_configured"}:
                logger.info(
                    "EmailVerifier: API verification unsuccessful for %s (status=%s). Fallback to SMTP.",
                    normalized_email,
                    verification_result.status,
                )
                verification_result = None

        if verification_result is None and self.method_preference in {"smtp", "both"}:
            verification_result = await self.verify_email_smtp(normalized_email)

        if verification_result is None:
            verification_result = EmailVerificationResult(
                valid=False,
                status="not_attempted",
                method=self.method_preference,
                message="No verification method executed.",
            )

        verification_result.verified_at = datetime.now(timezone.utc)

        if redis_client and (verification_result.status not in {"rate_limited", "not_attempted"}):
            try:
                await redis_client.setex(cache_key, self.cache_ttl, verification_result.to_json())
            except Exception:  # pragma: no cover - caching best effort
                logger.debug("EmailVerifier: failed to persist cache for %s", normalized_email)

        return verification_result

    async def batch_verify_emails(
        self,
        emails: Iterable[str],
        max_concurrent: int | None = None,
    ) -> dict[str, EmailVerificationResult]:
        unique_emails = {email.strip().lower() for email in emails if email}
        if not unique_emails:
            return {}

        concurrency = max_concurrent or self.max_concurrent or 5
        semaphore = asyncio.Semaphore(concurrency)

        async def _verify(email_address: str) -> Tuple[str, EmailVerificationResult]:
            async with semaphore:
                result = await self.verify_email(email_address)
                return email_address, result

        tasks = [asyncio.create_task(_verify(email)) for email in unique_emails]
        results: dict[str, EmailVerificationResult] = {}

        for future in asyncio.as_completed(tasks):
            email_address, result = await future
            results[email_address] = result

        return results


__all__ = [
    "EmailVerifier",
    "EmailVerificationError",
    "EmailVerificationRateLimited",
    "EmailVerificationResult",
]
