"""
Webhook API Endpoints
Webhook Management für Event Notifications
"""

import logging
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.database.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


class WebhookCreate(BaseModel):
    """Webhook Creation Schema"""

    url: HttpUrl
    events: list[str]  # ["job.completed", "job.failed", "company.created", etc.]
    secret: str | None = None  # Optional HMAC secret
    active: bool = True


class WebhookResponse(BaseModel):
    """Webhook Response Schema"""

    id: int
    url: str
    events: list[str]
    active: bool
    created_at: datetime


# In-Memory Webhook Storage (TODO: Move to Database)
WEBHOOKS: dict[int, dict[str, Any]] = {}
WEBHOOK_ID_COUNTER = 1


@router.post("/", response_model=WebhookResponse)
async def create_webhook(
    webhook: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Erstellt einen neuen Webhook

    **Permissions:** Authenticated users only

    **Supported Events:**
    - `job.completed` - Scraping Job abgeschlossen
    - `job.failed` - Scraping Job fehlgeschlagen
    - `job.started` - Scraping Job gestartet
    - `company.created` - Neue Company erstellt
    - `company.updated` - Company aktualisiert
    - `company.deleted` - Company gelöscht
    - `scoring.completed` - Lead Scoring abgeschlossen

    **Example:**
    ```json
    {
        "url": "https://your-app.com/webhooks/scraper",
        "events": ["job.completed", "job.failed"],
        "secret": "your-secret-key",
        "active": true
    }
    ```
    """
    global WEBHOOK_ID_COUNTER

    try:
        webhook_id = WEBHOOK_ID_COUNTER
        WEBHOOK_ID_COUNTER += 1

        webhook_data = {
            "id": webhook_id,
            "url": str(webhook.url),
            "events": webhook.events,
            "secret": webhook.secret,
            "active": webhook.active,
            "user_id": current_user.id,
            "created_at": datetime.now(),
        }

        WEBHOOKS[webhook_id] = webhook_data

        logger.info(
            f"Webhook created: ID={webhook_id}, URL={webhook.url}, "
            f"Events={webhook.events} (user: {current_user.username})"
        )

        return webhook_data

    except Exception as e:
        logger.error(f"Webhook creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook creation failed: {str(e)}") from e


@router.get("/", response_model=list[WebhookResponse])
async def list_webhooks(
    current_user: User = Depends(get_current_active_user),
) -> list[dict[str, Any]]:
    """
    Listet alle Webhooks des Users

    **Permissions:** Authenticated users only
    """
    user_webhooks = [
        {
            "id": wh["id"],
            "url": wh["url"],
            "events": wh["events"],
            "active": wh["active"],
            "created_at": wh["created_at"],
        }
        for wh in WEBHOOKS.values()
        if wh["user_id"] == current_user.id
    ]

    return user_webhooks


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: int,
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Holt einen spezifischen Webhook

    **Permissions:** Authenticated users only
    """
    webhook = WEBHOOKS.get(webhook_id)

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    if webhook["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return {
        "id": webhook["id"],
        "url": webhook["url"],
        "events": webhook["events"],
        "active": webhook["active"],
        "created_at": webhook["created_at"],
    }


@router.patch("/{webhook_id}")
async def update_webhook(
    webhook_id: int,
    active: bool | None = None,
    events: list[str] | None = None,
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Aktualisiert einen Webhook

    **Permissions:** Authenticated users only
    """
    webhook = WEBHOOKS.get(webhook_id)

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    if webhook["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if active is not None:
        webhook["active"] = active

    if events is not None:
        webhook["events"] = events

    logger.info(f"Webhook updated: ID={webhook_id} (user: {current_user.username})")

    return {
        "id": webhook["id"],
        "url": webhook["url"],
        "events": webhook["events"],
        "active": webhook["active"],
        "created_at": webhook["created_at"],
    }


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: int,
    current_user: User = Depends(get_current_active_user),
) -> dict[str, str]:
    """
    Löscht einen Webhook

    **Permissions:** Authenticated users only
    """
    webhook = WEBHOOKS.get(webhook_id)

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    if webhook["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    del WEBHOOKS[webhook_id]

    logger.info(f"Webhook deleted: ID={webhook_id} (user: {current_user.username})")

    return {"message": "Webhook deleted successfully"}


@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
) -> dict[str, str]:
    """
    Testet einen Webhook durch Senden eines Test-Events

    **Permissions:** Authenticated users only
    """
    webhook = WEBHOOKS.get(webhook_id)

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    if webhook["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Test Event senden
    test_payload = {
        "event": "webhook.test",
        "webhook_id": webhook_id,
        "timestamp": datetime.now().isoformat(),
        "data": {
            "message": "This is a test webhook event",
            "user": current_user.username,
        },
    }

    background_tasks.add_task(
        send_webhook_event, webhook["url"], test_payload, webhook.get("secret")
    )

    return {"message": "Test webhook event queued"}


# Helper Functions


async def send_webhook_event(url: str, payload: dict[str, Any], secret: str | None = None):
    """
    Sendet ein Webhook Event an eine URL

    Args:
        url: Webhook URL
        payload: Event Payload
        secret: Optional HMAC secret für Signatur
    """
    try:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "KR-Lead-Scraper-Webhook/1.0",
        }

        # TODO: Add HMAC signature if secret provided
        # if secret:
        #     signature = generate_hmac_signature(payload, secret)
        #     headers["X-Webhook-Signature"] = signature

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"Webhook sent successfully: {url} - Status: {response.status_code}")
            else:
                logger.warning(
                    f"Webhook failed: {url} - Status: {response.status_code} - "
                    f"Response: {response.text[:200]}"
                )

    except httpx.TimeoutException:
        logger.error(f"Webhook timeout: {url}")
    except Exception as e:
        logger.error(f"Webhook error: {url} - {e}")


async def trigger_webhook_event(event_type: str, data: dict[str, Any]):
    """
    Triggert Webhook Events für alle registrierten Webhooks

    Args:
        event_type: Event Type (z.B. "job.completed")
        data: Event Data
    """
    payload = {
        "event": event_type,
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }

    # Finde alle aktiven Webhooks die dieses Event abonniert haben
    matching_webhooks = [
        wh for wh in WEBHOOKS.values() if wh["active"] and event_type in wh["events"]
    ]

    logger.info(f"Triggering webhook event: {event_type} - {len(matching_webhooks)} webhooks")

    # Sende an alle matching Webhooks
    for webhook in matching_webhooks:
        try:
            await send_webhook_event(webhook["url"], payload, webhook.get("secret"))
        except Exception as e:
            logger.error(f"Failed to send webhook {webhook['id']}: {e}")
