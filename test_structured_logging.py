"""
Test Structured Logging
Demonstriert JSON-basiertes Logging mit Correlation IDs
"""

from app.utils.structured_logger import (
    clear_correlation_id,
    get_structured_logger,
    set_correlation_id,
)

# Get logger
logger = get_structured_logger(__name__)


def test_basic_logging():
    """Test basic logging"""
    print("=" * 60)
    print("Test 1: Basic Logging")
    print("=" * 60)

    logger.info("Simple info message")
    logger.debug("Debug message with details", user_id=123, action="login")
    logger.warning("Warning message", threshold=90, current_value=95)
    logger.error("Error occurred", error_code="E001", module="auth")

    print()


def test_correlation_id():
    """Test correlation ID tracking"""
    print("=" * 60)
    print("Test 2: Correlation ID Tracking")
    print("=" * 60)

    # Set correlation ID
    set_correlation_id("req-12345-abcde")

    logger.info("Request started", endpoint="/api/users", method="GET")
    logger.info("Database query", table="users", query_time_ms=45.2)
    logger.info("Request completed", status_code=200, duration_ms=120.5)

    # Clear correlation ID
    clear_correlation_id()

    logger.info("New request without correlation ID")

    print()


def test_exception_logging():
    """Test exception logging"""
    print("=" * 60)
    print("Test 3: Exception Logging")
    print("=" * 60)

    try:
        # Simulate error
        result = 1 / 0
    except Exception:
        logger.exception("Division by zero error", operation="divide", numerator=1, denominator=0)

    print()


def test_structured_data():
    """Test logging with structured data"""
    print("=" * 60)
    print("Test 4: Structured Data Logging")
    print("=" * 60)

    # Simulate API request logging
    logger.info(
        "API request processed",
        request_id="req-789",
        user_id=456,
        endpoint="/api/companies",
        method="POST",
        status_code=201,
        duration_ms=234.5,
        response_size_bytes=1024,
        user_agent="Mozilla/5.0",
        ip_address="192.168.1.100",
    )

    # Simulate database operation
    logger.info(
        "Database operation",
        operation="INSERT",
        table="companies",
        rows_affected=1,
        query_time_ms=12.3,
        transaction_id="tx-abc123",
    )

    # Simulate scraping job
    logger.info(
        "Scraping job completed",
        job_id=123,
        source="gelbe_seiten",
        city="Stuttgart",
        industry="IT",
        results_found=45,
        new_companies=12,
        updated_companies=8,
        duration_seconds=120.5,
        pages_scraped=5,
    )

    print()


def main():
    """Run all tests"""
    print("\n")
    print("🔍 Testing Structured Logging")
    print("=" * 60)
    print()
    print("📝 JSON logs are written to: logs/scraper_json.log")
    print("📝 Console logs are human-readable")
    print()

    test_basic_logging()
    test_correlation_id()
    test_exception_logging()
    test_structured_data()

    print("=" * 60)
    print("✅ All logging tests completed!")
    print("=" * 60)
    print()
    print("💡 Check logs/scraper_json.log for JSON-formatted logs")
    print()


if __name__ == "__main__":
    main()
