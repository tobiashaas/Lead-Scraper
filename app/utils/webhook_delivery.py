"""
Webhook Delivery Service
Handles secure webhook delivery with retry logic and HMAC signatures
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class WebhookDeliveryService:
    """Service for delivering webhooks to external endpoints"""

    def __init__(self, max_retries: int = 3, timeout: int = 10):
        """
        Initialize webhook delivery service

        Args:
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
        """
        self.max_retries = max_retries
        self.timeout = timeout

    def _generate_signature(self, payload: str, secret: str) -> str:
        """
        Generate HMAC-SHA256 signature for webhook payload

        Args:
            payload: JSON payload as string
            secret: Webhook secret key

        Returns:
            HMAC signature as hex string
        """
        return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    async def deliver_webhook(
        self,
        url: str,
        event: str,
        payload: dict[str, Any],
        secret: str | None = None,
        webhook_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Deliver webhook to external endpoint with retry logic

        Args:
            url: Webhook endpoint URL
            event: Event type (e.g., "job.completed")
            payload: Event payload data
            secret: Optional secret for HMAC signature
            webhook_id: Optional webhook ID for logging

        Returns:
            Delivery result with status and metadata
        """
        # Prepare webhook payload
        webhook_payload = {
            "event": event,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload,
        }

        payload_json = json.dumps(webhook_payload, default=str)

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Lead-Scraper-Webhook/1.0",
            "X-Webhook-Event": event,
        }

        # Add HMAC signature if secret provided
        if secret:
            signature = self._generate_signature(payload_json, secret)
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        # Attempt delivery with retries
        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, content=payload_json, headers=headers)

                    # Success
                    if response.status_code < 400:
                        logger.info(
                            f"Webhook delivered successfully: webhook_id={webhook_id}, "
                            f"event={event}, url={url}, status={response.status_code}, "
                            f"attempt={attempt + 1}"
                        )
                        return {
                            "success": True,
                            "status_code": response.status_code,
                            "attempt": attempt + 1,
                            "response": response.text[:500],  # Limit response size
                        }

                    # Client/Server error - log and retry
                    logger.warning(
                        f"Webhook delivery failed: webhook_id={webhook_id}, "
                        f"event={event}, url={url}, status={response.status_code}, "
                        f"attempt={attempt + 1}/{self.max_retries}"
                    )
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"

            except httpx.TimeoutException as e:
                logger.warning(
                    f"Webhook delivery timeout: webhook_id={webhook_id}, "
                    f"event={event}, url={url}, attempt={attempt + 1}/{self.max_retries}"
                )
                last_error = f"Timeout: {str(e)}"

            except Exception as e:
                logger.error(
                    f"Webhook delivery error: webhook_id={webhook_id}, "
                    f"event={event}, url={url}, error={str(e)}, "
                    f"attempt={attempt + 1}/{self.max_retries}"
                )
                last_error = str(e)

            # Exponential backoff before retry (except on last attempt)
            if attempt < self.max_retries - 1:
                import asyncio

                await asyncio.sleep(2**attempt)  # 1s, 2s, 4s, ...

        # All retries failed
        logger.error(
            f"Webhook delivery failed after {self.max_retries} attempts: "
            f"webhook_id={webhook_id}, event={event}, url={url}, "
            f"last_error={last_error}"
        )
        return {
            "success": False,
            "error": last_error,
            "attempts": self.max_retries,
        }

    async def trigger_webhooks(
        self, event: str, payload: dict[str, Any], webhooks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Trigger multiple webhooks for an event

        Args:
            event: Event type
            payload: Event payload
            webhooks: List of webhook configurations

        Returns:
            List of delivery results
        """
        results = []

        for webhook in webhooks:
            # Skip inactive webhooks
            if not webhook.get("active", True):
                continue

            # Check if webhook is subscribed to this event
            if event not in webhook.get("events", []):
                continue

            # Deliver webhook
            result = await self.deliver_webhook(
                url=webhook["url"],
                event=event,
                payload=payload,
                secret=webhook.get("secret"),
                webhook_id=webhook.get("id"),
            )

            results.append(
                {
                    "webhook_id": webhook.get("id"),
                    "url": webhook["url"],
                    "event": event,
                    **result,
                }
            )

        return results


# Global webhook delivery service instance
webhook_service = WebhookDeliveryService()
