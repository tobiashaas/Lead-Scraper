"""
Logging Helpers
Convenience functions for common logging patterns
"""

import time
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps

from app.utils.structured_logger import get_structured_logger

logger = get_structured_logger(__name__)


@contextmanager
def log_operation(operation_name: str, **context):
    """
    Context manager for logging operations with timing

    Usage:
        with log_operation("database_query", table="users"):
            # Your code here
            pass
    """
    start_time = time.time()

    logger.info(f"{operation_name} started", **context)

    try:
        yield
        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"{operation_name} completed", duration_ms=round(duration_ms, 2), **context)
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"{operation_name} failed",
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=round(duration_ms, 2),
            **context,
        )
        raise


def log_function_call(func: Callable) -> Callable:
    """
    Decorator for logging function calls

    Usage:
        @log_function_call
        def my_function(arg1, arg2):
            pass
    """

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        func_logger = get_structured_logger(func.__module__)
        start_time = time.time()

        func_logger.debug(
            f"Calling {func.__name__}", function=func.__name__, module=func.__module__
        )

        try:
            result = await func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000

            func_logger.debug(
                f"{func.__name__} completed",
                function=func.__name__,
                duration_ms=round(duration_ms, 2),
            )

            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            func_logger.error(
                f"{func.__name__} failed",
                function=func.__name__,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration_ms, 2),
            )
            raise

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        func_logger = get_structured_logger(func.__module__)
        start_time = time.time()

        func_logger.debug(
            f"Calling {func.__name__}", function=func.__name__, module=func.__module__
        )

        try:
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000

            func_logger.debug(
                f"{func.__name__} completed",
                function=func.__name__,
                duration_ms=round(duration_ms, 2),
            )

            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            func_logger.error(
                f"{func.__name__} failed",
                function=func.__name__,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration_ms, 2),
            )
            raise

    # Return appropriate wrapper based on function type
    import asyncio

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


def log_api_request(method: str, path: str, status_code: int, duration_ms: float, **extra):
    """
    Log API request

    Args:
        method: HTTP method
        path: Request path
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        **extra: Additional context
    """
    logger.info(
        "API request",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=round(duration_ms, 2),
        **extra,
    )


def log_database_query(
    operation: str, table: str, duration_ms: float, rows_affected: int | None = None, **extra
):
    """
    Log database query

    Args:
        operation: SQL operation (SELECT, INSERT, UPDATE, DELETE)
        table: Table name
        duration_ms: Query duration in milliseconds
        rows_affected: Number of rows affected
        **extra: Additional context
    """
    logger.info(
        "Database query",
        operation=operation,
        table=table,
        duration_ms=round(duration_ms, 2),
        rows_affected=rows_affected,
        **extra,
    )


def log_scraping_job(job_id: int, source: str, status: str, **extra):
    """
    Log scraping job event

    Args:
        job_id: Job ID
        source: Scraping source
        status: Job status
        **extra: Additional context
    """
    logger.info("Scraping job", job_id=job_id, source=source, status=status, **extra)


def log_authentication(event: str, username: str, success: bool, **extra):
    """
    Log authentication event

    Args:
        event: Event type (login, logout, register, etc.)
        username: Username
        success: Whether the event was successful
        **extra: Additional context
    """
    logger.info("Authentication event", event=event, username=username, success=success, **extra)
