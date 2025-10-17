"""
Sentry Middleware
Adds additional context to Sentry events
"""

from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.sentry import set_context, add_breadcrumb, set_user_context
from app.core.config import settings


class SentryContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request context to Sentry events
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add request context to Sentry

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response
        """

        if not settings.sentry_enabled:
            return await call_next(request)

        # Add request context
        set_context(
            "request_details",
            {
                "url": str(request.url),
                "method": request.method,
                "headers": dict(request.headers),
                "path_params": request.path_params,
                "query_params": dict(request.query_params),
            },
        )

        # Add breadcrumb for request
        add_breadcrumb(
            message=f"{request.method} {request.url.path}",
            category="request",
            level="info",
            data={
                "method": request.method,
                "url": str(request.url),
            },
        )

        # Set user context if authenticated
        if hasattr(request.state, "user"):
            user = request.state.user
            set_user_context(user_id=user.id, username=user.username, email=user.email)

        # Process request
        response = await call_next(request)

        # Add response breadcrumb
        add_breadcrumb(
            message=f"Response {response.status_code}",
            category="response",
            level="info" if response.status_code < 400 else "error",
            data={
                "status_code": response.status_code,
            },
        )

        return response
