"""
Sentry Error Tracking Configuration
Initialisiert Sentry für Error Tracking und Performance Monitoring
"""

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from app.core.config import settings
from app.utils.structured_logger import get_structured_logger

logger = get_structured_logger(__name__)


def init_sentry():
    """
    Initialize Sentry SDK

    Features:
    - Error tracking
    - Performance monitoring
    - Release tracking
    - User context
    - Custom tags and context
    """

    if not settings.sentry_enabled or not settings.sentry_dsn:
        logger.info("Sentry is disabled or DSN not configured")
        return

    try:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.sentry_environment,
            # Performance Monitoring
            traces_sample_rate=settings.sentry_traces_sample_rate,
            profiles_sample_rate=settings.sentry_profiles_sample_rate,
            # Integrations
            integrations=[
                FastApiIntegration(
                    transaction_style="endpoint",  # Group by endpoint
                    failed_request_status_codes=[403, range(500, 599)],
                ),
                SqlalchemyIntegration(),
                RedisIntegration(),
                LoggingIntegration(
                    level=None,  # Capture all levels
                    event_level=None,  # Don't create events from logs
                ),
            ],
            # Release tracking
            release=f"kr-lead-scraper@{settings.app_version}",
            # Additional options
            attach_stacktrace=True,
            send_default_pii=False,  # Don't send PII by default
            max_breadcrumbs=50,
            # Custom before_send hook
            before_send=before_send_hook,
            # Custom before_send_transaction hook
            before_send_transaction=before_send_transaction_hook,
        )

        # Set global tags
        sentry_sdk.set_tag("app_name", settings.app_name)
        sentry_sdk.set_tag("environment", settings.environment)

        logger.info(
            "Sentry initialized",
            environment=settings.sentry_environment,
            traces_sample_rate=settings.sentry_traces_sample_rate,
        )

    except Exception as e:
        logger.error("Failed to initialize Sentry", error=str(e), error_type=type(e).__name__)


def before_send_hook(event, hint):
    """
    Hook called before sending event to Sentry
    Can be used to filter or modify events

    Args:
        event: Event data
        hint: Additional context

    Returns:
        Modified event or None to drop event
    """

    # Filter out specific errors if needed
    if "exc_info" in hint:
        exc_type, exc_value, tb = hint["exc_info"]

        # Example: Don't send validation errors to Sentry
        if exc_type.__name__ == "ValidationError":
            return None

    # Add custom context
    event.setdefault("tags", {})
    event["tags"]["app_version"] = settings.app_version

    return event


def before_send_transaction_hook(event, hint):
    """
    Hook called before sending transaction to Sentry

    Args:
        event: Transaction data
        hint: Additional context

    Returns:
        Modified event or None to drop event
    """

    # Filter out health check transactions if needed
    if event.get("transaction", "").startswith("/health"):
        return None

    return event


def capture_exception(error: Exception, **context):
    """
    Capture exception with custom context

    Args:
        error: Exception to capture
        **context: Additional context data
    """

    if not settings.sentry_enabled:
        return

    with sentry_sdk.push_scope() as scope:
        # Add custom context
        for key, value in context.items():
            scope.set_context(key, value)

        sentry_sdk.capture_exception(error)


def capture_message(message: str, level: str = "info", **context):
    """
    Capture message with custom context

    Args:
        message: Message to capture
        level: Message level (debug, info, warning, error, fatal)
        **context: Additional context data
    """

    if not settings.sentry_enabled:
        return

    with sentry_sdk.push_scope() as scope:
        # Add custom context
        for key, value in context.items():
            scope.set_context(key, value)

        sentry_sdk.capture_message(message, level=level)


def set_user_context(user_id: int, username: str, **extra):
    """
    Set user context for error tracking

    Args:
        user_id: User ID
        username: Username
        **extra: Additional user data
    """

    if not settings.sentry_enabled:
        return

    sentry_sdk.set_user({"id": user_id, "username": username, **extra})


def set_context(context_name: str, context_data: dict):
    """
    Set custom context

    Args:
        context_name: Context name
        context_data: Context data
    """

    if not settings.sentry_enabled:
        return

    sentry_sdk.set_context(context_name, context_data)


def add_breadcrumb(message: str, category: str = "default", level: str = "info", **data):
    """
    Add breadcrumb for debugging

    Args:
        message: Breadcrumb message
        category: Breadcrumb category
        level: Breadcrumb level
        **data: Additional data
    """

    if not settings.sentry_enabled:
        return

    sentry_sdk.add_breadcrumb(message=message, category=category, level=level, data=data)


def start_transaction(name: str, op: str = "task") -> sentry_sdk.tracing.Transaction:
    """
    Start a performance transaction

    Args:
        name: Transaction name
        op: Operation type

    Returns:
        Transaction object
    """

    if not settings.sentry_enabled:
        # Return a no-op transaction
        class NoOpTransaction:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def start_child(self, *args, **kwargs):
                return NoOpTransaction()

        return NoOpTransaction()

    return sentry_sdk.start_transaction(name=name, op=op)
