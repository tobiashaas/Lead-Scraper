"""
Webhook Helper Functions
Easy-to-use functions for triggering webhooks from anywhere in the app
"""

import logging
from typing import Any

from app.api.webhooks import WEBHOOKS
from app.utils.webhook_delivery import webhook_service

logger = logging.getLogger(__name__)


async def trigger_webhook_event(event: str, payload: dict[str, Any]) -> None:
    """
    Trigger webhook event - fire and forget

    Args:
        event: Event type (e.g., "job.completed")
        payload: Event payload data

    Example:
        await trigger_webhook_event("job.completed", {
            "job_id": 123,
            "status": "completed",
            "companies_found": 50
        })
    """
    try:
        # Get all webhooks from in-memory storage
        webhooks = list(WEBHOOKS.values())

        if not webhooks:
            logger.debug(f"No webhooks configured for event: {event}")
            return

        # Trigger webhooks asynchronously
        results = await webhook_service.trigger_webhooks(event, payload, webhooks)

        # Log summary
        success_count = sum(1 for r in results if r.get("success"))
        logger.info(
            f"Webhook event triggered: event={event}, "
            f"webhooks={len(results)}, successful={success_count}"
        )

    except Exception as e:
        logger.error(f"Failed to trigger webhook event: event={event}, error={str(e)}")


def trigger_webhook_event_background(event: str, payload: dict[str, Any]) -> None:
    """
    Trigger webhook event in background (non-blocking)

    Use this when you don't want to await the webhook delivery

    Args:
        event: Event type
        payload: Event payload data
    """
    import asyncio

    try:
        # Create task in background
        asyncio.create_task(trigger_webhook_event(event, payload))
    except Exception as e:
        logger.error(f"Failed to create background webhook task: event={event}, error={str(e)}")
