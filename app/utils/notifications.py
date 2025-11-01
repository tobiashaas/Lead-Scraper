"""Notification service and multi-channel alerting utilities."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Optional

import httpx
import redis.asyncio as redis
from aiosmtplib import SMTP, SMTPException
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from app.core.config import settings

logger = logging.getLogger(__name__)

TEMPLATES_PATH = Path(__file__).resolve().parent.parent / "templates" / "alerts"
_TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(TEMPLATES_PATH),
    autoescape=select_autoescape(("html", "xml", "json")),
    trim_blocks=True,
    lstrip_blocks=True,
)


class NotificationChannel(ABC):
    """Abstract base class for notification delivery channels."""

    name: str

    @abstractmethod
    async def send(self, subject: str, message: str, **context: Any) -> bool:
        """Send a notification message."""

    @abstractmethod
    async def send_templated(self, template_name: str, context: dict[str, Any]) -> bool:
        """Send a notification using a predefined template."""


class EmailChannel(NotificationChannel):
    """SMTP-backed email notification channel."""

    def __init__(
        self,
        *,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_email: str,
        to_emails: Iterable[str],
        use_tls: bool = True,
    ) -> None:
        self.name = "email"
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.to_emails = [email.strip() for email in to_emails if email.strip()]
        self.use_tls = use_tls
        self._client: Optional[SMTP] = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> SMTP:
        async with self._client_lock:
            if self._client is not None and self._client.is_connected:
                return self._client

            client = SMTP(hostname=self.smtp_host, port=self.smtp_port, timeout=30)
            await client.connect()
            if self.use_tls:
                await client.starttls()
            if self.smtp_user:
                await client.login(self.smtp_user, self.smtp_password)

            self._client = client
            return client

    async def _send_email(self, message: EmailMessage) -> bool:
        try:
            client = await self._get_client()
            await client.send_message(message)
            return True
        except SMTPException as exc:
            logger.warning("EmailChannel failed to send email: %s", exc)
            async with self._client_lock:
                if self._client is not None:
                    try:
                        await self._client.quit()
                    except Exception:  # pragma: no cover - defensive
                        logger.debug("EmailChannel: failed to quit SMTP client", exc_info=True)
                    self._client = None
            return False

    async def send(self, subject: str, message: str, **context: Any) -> bool:
        """Send a plain text/HTML email message."""

        if not self.to_emails:
            logger.debug("EmailChannel skipped send - no recipients configured")
            return False

        text_body = context.get("text_body", message)
        html_body = context.get("html_body")

        email_message = EmailMessage()
        email_message["Subject"] = subject
        email_message["From"] = self.from_email
        email_message["To"] = ", ".join(self.to_emails)

        if html_body:
            email_message.set_content(text_body)
            email_message.add_alternative(html_body, subtype="html")
        else:
            email_message.set_content(text_body)

        return await self._send_email(email_message)

    async def send_templated(self, template_name: str, context: dict[str, Any]) -> bool:
        subject = context.get(
            "subject",
            f"[{context.get('environment', 'Env').upper()}] {template_name.replace('_', ' ').title()}",
        )
        text_body = render_template(f"{template_name}.txt", context)
        html_body = render_template(f"{template_name}.html", context)

        if text_body is None and html_body is None:
            logger.warning("EmailChannel template not found for %s", template_name)
            return False

        return await self.send(
            subject=subject,
            message=text_body or "",
            text_body=text_body or "",
            html_body=html_body,
        )


class SlackChannel(NotificationChannel):
    """Slack webhook notification channel."""

    def __init__(
        self,
        *,
        webhook_url: str,
        channel: str | None = None,
        username: str = "KR Lead Scraper",
        rate_limit_per_second: float = 1.0,
    ) -> None:
        self.name = "slack"
        self.webhook_url = webhook_url
        self.channel = channel
        self.username = username
        self.rate_limit_per_second = rate_limit_per_second
        self._lock = asyncio.Lock()
        self._last_sent_at = 0.0

    async def _respect_rate_limit(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_sent_at
            wait_for = max(0.0, (1.0 / self.rate_limit_per_second) - elapsed)
            if wait_for > 0:
                await asyncio.sleep(wait_for)
            self._last_sent_at = time.monotonic()

    async def send(self, subject: str, message: str, **context: Any) -> bool:
        if not self.webhook_url:
            logger.debug("SlackChannel skipped send - webhook URL not configured")
            return False

        payload: dict[str, Any] = {
            "text": message or subject,
        }

        severity = context.get("severity")
        color = {
            "critical": "danger",
            "warning": "warning",
            "info": "#439FE0",
            "success": "good",
        }.get(severity, "#439FE0")

        blocks = context.get("blocks")
        attachments = context.get("attachments")

        if blocks:
            payload["blocks"] = blocks
        if attachments:
            payload["attachments"] = attachments
        elif not blocks:
            payload["attachments"] = [
                {
                    "color": color,
                    "text": message,
                    "title": subject,
                }
            ]

        if self.channel:
            payload["channel"] = self.channel
        if self.username:
            payload["username"] = self.username

        await self._respect_rate_limit()

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(self.webhook_url, json=payload)
                if response.status_code >= 400:
                    logger.warning(
                        "SlackChannel failed with status %s: %s",
                        response.status_code,
                        response.text,
                    )
                    return False
        except httpx.HTTPError as exc:
            logger.warning("SlackChannel HTTP error: %s", exc)
            return False

        return True

    async def send_templated(self, template_name: str, context: dict[str, Any]) -> bool:
        subject = context.get("subject") or f"{template_name.replace('_', ' ').title()}"
        message = context.get("message") or subject
        rendered = render_template(f"{template_name}.json", context)

        if rendered is None:
            logger.debug("SlackChannel falling back to plain message for %s", template_name)
            return await self.send(
                subject=subject,
                message=message,
                severity=context.get("severity"),
            )

        try:
            payload = json.loads(rendered)
        except json.JSONDecodeError as exc:
            logger.error("SlackChannel template produced invalid JSON: %s", exc)
            return await self.send(
                subject=subject,
                message=message,
                severity=context.get("severity"),
            )

        subject = context.get("subject") or payload.get("fallback") or subject
        message = context.get("message") or payload.get("text", message)

        blocks = payload.get("blocks")
        attachments = payload.get("attachments")

        return await self.send(
            subject=subject,
            message=message,
            blocks=blocks,
            attachments=attachments,
            severity=context.get("severity"),
        )


class NotificationService:
    """High-level notification service dispatching to all configured channels."""

    def __init__(self, channels: Iterable[NotificationChannel]) -> None:
        self.channels = list(channels)
        self._redis: redis.Redis | None = None
        self._redis_lock = asyncio.Lock()

    async def send_alert(
        self,
        alert_type: str,
        severity: str,
        subject: str,
        message: str,
        **context: Any,
    ) -> dict[str, bool]:
        context_payload = {
            "alert_type": alert_type,
            "severity": severity,
            "timestamp": context.get("timestamp") or context.get("time"),
            "environment": context.get("environment") or settings.environment,
            **context,
        }

        discriminator = (
            context_payload.get("dedup_key")
            or context_payload.get("job_id")
            or context_payload.get("issue_type")
            or context_payload.get("resource_id")
            or context_payload.get("source")
            or "generic"
        )
        dedup_key = f"alert:{alert_type}:{discriminator}"

        logger.info(
            "Dispatching alert",
            extra={
                "alert_type": alert_type,
                "severity": severity,
                "channels": [channel.name for channel in self.channels],
                "context_keys": sorted(context_payload.keys()),
            },
        )

        if not self.channels:
            logger.debug(
                "NotificationService has no channels configured; skipping alert %s", alert_type
            )
            return {}

        redis_client: redis.Redis | None = None
        if settings.redis_url:
            redis_client = await self._get_redis()

        if redis_client and await redis_client.get(dedup_key):
            logger.debug("NotificationService skipped alert %s (recently sent)", dedup_key)
            return {channel.name: True for channel in self.channels}

        async def _send(channel: NotificationChannel) -> tuple[str, bool]:
            try:
                result = await channel.send(subject, message, **context_payload)
                return channel.name, result
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning(
                    "NotificationService channel %s failed: %s",
                    channel.name,
                    exc,
                    exc_info=True,
                )
                return channel.name, False

        results = await asyncio.gather(*[_send(channel) for channel in self.channels])

        if redis_client:
            try:
                await redis_client.setex(dedup_key, 300, "1")
            except Exception:  # pragma: no cover - best effort caching
                logger.debug(
                    "NotificationService failed to cache dedup key %s", dedup_key, exc_info=True
                )

        return {name: status for name, status in results}

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
                )
                await client.ping()
                self._redis = client
            except Exception as exc:  # pragma: no cover - cache optional
                logger.debug("NotificationService Redis unavailable: %s", exc)
                self._redis = None

        return self._redis

    async def get_redis_client(self) -> redis.Redis | None:
        """Expose Redis client for external rate limiting helpers (if available)."""

        return await self._get_redis()

    async def send_templated_alert(
        self,
        template_name: str,
        context: dict[str, Any],
    ) -> dict[str, bool]:
        context_with_defaults = dict(context)
        context_with_defaults.setdefault("alert_type", template_name)
        context_with_defaults.setdefault("severity", "warning")
        context_with_defaults.setdefault("environment", settings.environment)
        context_with_defaults.setdefault("timestamp", datetime.now(UTC).isoformat())

        alert_type = context_with_defaults["alert_type"]
        severity = context_with_defaults.get("severity", "warning")
        dedup_key = (
            context_with_defaults.get("dedup_key")
            or f"alert:{template_name}:{context_with_defaults.get('job_id') or context_with_defaults.get('issue_type') or context_with_defaults.get('queue_name') or 'generic'}"
        )
        dedup_key = str(dedup_key)

        logger.info(
            "Dispatching templated alert",
            extra={
                "alert_type": alert_type,
                "severity": severity,
                "template": template_name,
                "channels": [channel.name for channel in self.channels],
                "context_keys": sorted(context_with_defaults.keys()),
            },
        )

        if settings.redis_url:
            redis_client = await self._get_redis()
        else:
            redis_client = None

        if redis_client and await redis_client.get(dedup_key):
            logger.debug("NotificationService skipped alert %s (recently sent)", dedup_key)
            return {channel.name: True for channel in self.channels}

        if not self.channels:
            logger.debug(
                "NotificationService has no channels configured; skipping templated alert %s",
                template_name,
            )
            return {}

        async def _send(channel: NotificationChannel) -> tuple[str, bool]:
            try:
                result = await channel.send_templated(template_name, context_with_defaults)
                return channel.name, result
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning(
                    "NotificationService templated alert via %s failed: %s",
                    channel.name,
                    exc,
                    exc_info=True,
                )
                return channel.name, False

        results = await asyncio.gather(*[_send(channel) for channel in self.channels])

        if redis_client:
            try:
                await redis_client.setex(dedup_key, 300, "1")
            except Exception:  # pragma: no cover - best effort caching
                logger.debug(
                    "NotificationService failed to cache templated dedup key %s",
                    dedup_key,
                    exc_info=True,
                )

        return {name: status for name, status in results}


_notification_service: Optional[NotificationService] = None
_notification_lock = threading.Lock()


def render_template(template_filename: str, context: dict[str, Any]) -> str | None:
    try:
        template = _TEMPLATE_ENV.get_template(template_filename)
    except TemplateNotFound:
        return None

    return template.render(**context)


def get_notification_service() -> NotificationService:
    global _notification_service

    if _notification_service is not None:
        return _notification_service

    with _notification_lock:
        if _notification_service is not None:
            return _notification_service

        if not settings.alerting_enabled:
            _notification_service = NotificationService([])
            return _notification_service

        channels: list[NotificationChannel] = []

        if settings.alert_email_enabled and settings.alert_email_to:
            recipients = settings.alert_email_to.split(",")
            channels.append(
                EmailChannel(
                    smtp_host=settings.alert_smtp_host,
                    smtp_port=settings.alert_smtp_port,
                    smtp_user=settings.alert_smtp_user,
                    smtp_password=settings.alert_smtp_password,
                    from_email=settings.alert_from_email,
                    to_emails=recipients,
                    use_tls=settings.alert_smtp_use_tls,
                )
            )

        if settings.alert_slack_enabled and settings.alert_slack_webhook_url:
            channels.append(
                SlackChannel(
                    webhook_url=settings.alert_slack_webhook_url,
                    channel=settings.alert_slack_channel or None,
                    username=settings.alert_slack_username,
                )
            )

        _notification_service = NotificationService(channels)
        return _notification_service


__all__ = [
    "NotificationChannel",
    "EmailChannel",
    "SlackChannel",
    "NotificationService",
    "get_notification_service",
    "render_template",
]
