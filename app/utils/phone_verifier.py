"""Phone verification utilities leveraging phonenumbers with optional provider integrations."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Tuple

import phonenumbers
from phonenumbers import carrier, geocoder, NumberParseException, PhoneNumber

try:  # Optional dependencies for reachability lookups
    import httpx
except ImportError:  # pragma: no cover - optional dependency
    httpx = None  # type: ignore

import redis.asyncio as redis

from app.core.config import settings


logger = logging.getLogger(__name__)


PHONE_CACHE_PREFIX = "phone_verification:"


@dataclass(slots=True)
class PhoneVerificationResult:
    """Structured result for phone verification operations."""

    valid: bool
    formatted_e164: str | None
    status: str
    number_type: str | None = None
    carrier: str | None = None
    location: str | None = None
    country_code: int | None = None
    national_number: int | None = None
    reachable: bool | None = None
    method: str = "phonenumbers"
    message: str | None = None
    cached: bool = False
    verified_at: datetime | None = None

    def to_json(self) -> str:
        payload = {
            "valid": self.valid,
            "formatted_e164": self.formatted_e164,
            "status": self.status,
            "number_type": self.number_type,
            "carrier": self.carrier,
            "location": self.location,
            "country_code": self.country_code,
            "national_number": self.national_number,
            "reachable": self.reachable,
            "method": self.method,
            "message": self.message,
            "cached": self.cached,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
        }
        return json.dumps(payload)

    @classmethod
    def from_serialized(cls, payload: str) -> "PhoneVerificationResult":
        data = json.loads(payload)
        verified_at = (
            datetime.fromisoformat(data["verified_at"]).astimezone(timezone.utc)
            if data.get("verified_at")
            else None
        )
        return cls(
            valid=data.get("valid", False),
            formatted_e164=data.get("formatted_e164"),
            status=data.get("status", "unknown"),
            number_type=data.get("number_type"),
            carrier=data.get("carrier"),
            location=data.get("location"),
            country_code=data.get("country_code"),
            national_number=data.get("national_number"),
            reachable=data.get("reachable"),
            method=data.get("method", "phonenumbers"),
            message=data.get("message"),
            cached=data.get("cached", False),
            verified_at=verified_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "formatted_e164": self.formatted_e164,
            "status": self.status,
            "number_type": self.number_type,
            "carrier": self.carrier,
            "location": self.location,
            "country_code": self.country_code,
            "national_number": self.national_number,
            "reachable": self.reachable,
            "method": self.method,
            "message": self.message,
            "cached": self.cached,
            "verified_at": self.verified_at,
        }


class PhoneVerifier:
    """Phone verification utility using phonenumbers metadata and optional reachability APIs."""

    def __init__(self) -> None:
        self.default_region = "DE"
        self.cache_ttl = settings.email_verification_cache_ttl  # reuse same TTL
        self.api_provider = (settings.phone_verification_api_provider or "").lower()
        self.api_key = settings.phone_verification_api_key

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
                logger.warning("PhoneVerifier: Redis connection unavailable: %s", exc)
                self._redis = None
        return self._redis

    async def close(self) -> None:
        if self._redis:
            try:
                await self._redis.close()
            except Exception:  # pragma: no cover - best effort
                logger.debug("PhoneVerifier: failed to close redis", exc_info=True)
            finally:
                self._redis = None

    @staticmethod
    def normalize_phone_for_comparison(phone: str, default_region: str = "DE") -> str | None:
        try:
            parsed = phonenumbers.parse(phone, default_region)
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except NumberParseException:
            return None

    @staticmethod
    def _map_number_type(number_type: int) -> str:
        type_mapping = {
            phonenumbers.NumberType.MOBILE: "mobile",
            phonenumbers.NumberType.FIXED_LINE: "fixed_line",
            phonenumbers.NumberType.FIXED_LINE_OR_MOBILE: "fixed_line_or_mobile",
            phonenumbers.NumberType.TOLL_FREE: "toll_free",
            phonenumbers.NumberType.PREMIUM_RATE: "premium_rate",
            phonenumbers.NumberType.SHARED_COST: "shared_cost",
            phonenumbers.NumberType.VOIP: "voip",
            phonenumbers.NumberType.PERSONAL_NUMBER: "personal",
            phonenumbers.NumberType.PAGER: "pager",
            phonenumbers.NumberType.UAN: "uan",
            phonenumbers.NumberType.VOICEMAIL: "voicemail",
            phonenumbers.NumberType.UNKNOWN: "unknown",
        }
        return type_mapping.get(number_type, "unknown")

    @staticmethod
    def _base_verification(parsed: PhoneNumber, region: str) -> PhoneVerificationResult:
        is_valid = phonenumbers.is_valid_number(parsed)
        formatted_e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        number_type = PhoneVerifier._map_number_type(phonenumbers.number_type(parsed))
        carrier_name = carrier.name_for_number(parsed, region.lower())
        location = geocoder.description_for_number(parsed, region.lower())

        return PhoneVerificationResult(
            valid=is_valid,
            formatted_e164=formatted_e164,
            status="valid" if is_valid else "invalid",
            number_type=number_type,
            carrier=carrier_name or None,
            location=location or None,
            country_code=parsed.country_code,
            national_number=parsed.national_number,
        )

    async def verify_phone_enhanced(
        self, phone: str, country: str | None = None, use_cache: bool = True
    ) -> PhoneVerificationResult:
        region = (country or self.default_region).upper()
        redis_client = await self._get_redis()
        cache_key = f"{PHONE_CACHE_PREFIX}{region}:{phone.strip()}"

        if use_cache and redis_client:
            cached = await redis_client.get(cache_key)
            if cached:
                result = PhoneVerificationResult.from_serialized(cached)
                result.cached = True
                return result

        try:
            parsed = phonenumbers.parse(phone, region)
        except NumberParseException:
            result = PhoneVerificationResult(
                valid=False,
                formatted_e164=None,
                status="invalid_format",
                message="Phone number could not be parsed.",
            )
            result.verified_at = datetime.now(timezone.utc)
            return result

        result = self._base_verification(parsed, region)
        result.verified_at = datetime.now(timezone.utc)

        # Optional reachability check via API (e.g., Twilio)
        if result.valid and self.api_provider and self.api_key:
            reachability = await self.verify_phone_reachability(result.formatted_e164 or phone)
            if reachability:
                result.reachable = reachability.reachable
                result.method = reachability.method
                result.message = reachability.message
                if reachability.carrier:
                    result.carrier = reachability.carrier
                if reachability.number_type:
                    result.number_type = reachability.number_type

        if redis_client:
            try:
                await redis_client.setex(cache_key, self.cache_ttl, result.to_json())
            except Exception:  # pragma: no cover - caching best effort
                logger.debug("PhoneVerifier: failed to persist cache for %s", phone)

        return result

    @dataclass(slots=True)
    class ReachabilityResult:
        reachable: bool | None
        number_type: str | None
        carrier: str | None
        method: str
        message: str | None

    async def verify_phone_reachability(self, phone: str) -> ReachabilityResult | None:
        if not self.api_provider or not self.api_key:
            return None

        if self.api_provider == "twilio":
            if httpx is None:  # pragma: no cover - optional dependency missing
                logger.warning("PhoneVerifier: httpx not installed, cannot call Twilio Lookup API")
                return None

            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(
                        f"https://lookups.twilio.com/v1/PhoneNumbers/{phone}",
                        params={"Type": "carrier"},
                        auth=(self.api_key, self.api_key),
                    )
                    if response.status_code == 200:
                        payload = response.json()
                        carrier_info = payload.get("carrier", {})
                        return self.ReachabilityResult(
                            reachable=True,
                            number_type=(carrier_info.get("type") or "unknown").lower(),
                            carrier=carrier_info.get("name"),
                            method="twilio",
                            message=None,
                        )
                    if response.status_code == 404:
                        return self.ReachabilityResult(
                            reachable=False,
                            number_type="unknown",
                            carrier=None,
                            method="twilio",
                            message="Number not found",
                        )
                    return self.ReachabilityResult(
                        reachable=None,
                        number_type="unknown",
                        carrier=None,
                        method="twilio",
                        message=f"Unexpected status code {response.status_code}",
                    )
            except Exception as exc:  # pragma: no cover - network variability
                logger.warning("PhoneVerifier: Twilio lookup failed for %s: %s", phone, exc)
                return self.ReachabilityResult(
                    reachable=None,
                    number_type="unknown",
                    carrier=None,
                    method="twilio",
                    message=str(exc),
                )

        # Other providers can be added here
        logger.debug("PhoneVerifier: Unsupported phone verification provider %s", self.api_provider)
        return None

    async def batch_verify_phones(
        self,
        phones: Iterable[str],
        country: str | None = None,
        max_concurrent: int | None = None,
    ) -> dict[str, PhoneVerificationResult]:
        region = (country or self.default_region).upper()
        unique_phones = {phone.strip() for phone in phones if phone}
        if not unique_phones:
            return {}

        concurrency = max_concurrent or settings.verification_max_concurrent or 5
        semaphore = asyncio.Semaphore(concurrency)

        async def _verify(phone_number: str) -> Tuple[str, PhoneVerificationResult]:
            async with semaphore:
                result = await self.verify_phone_enhanced(phone_number, country=region)
                return phone_number, result

        tasks = [asyncio.create_task(_verify(phone)) for phone in unique_phones]
        results: dict[str, PhoneVerificationResult] = {}

        for future in asyncio.as_completed(tasks):
            phone_number, result = await future
            results[phone_number] = result

        return results


__all__ = [
    "PhoneVerifier",
    "PhoneVerificationResult",
]
