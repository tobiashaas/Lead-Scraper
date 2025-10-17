"""
Test Sentry Integration
Demonstriert Sentry Error Tracking und Performance Monitoring
"""

from app.core.config import settings
from app.core.sentry import (
    add_breadcrumb,
    capture_exception,
    capture_message,
    set_context,
    set_user_context,
    start_transaction,
)

print("=" * 60)
print("Sentry Integration Test")
print("=" * 60)
print()

# Check if Sentry is enabled
if not settings.sentry_enabled:
    print("⚠️  Sentry is DISABLED")
    print()
    print("To enable Sentry:")
    print("1. Set SENTRY_ENABLED=true in .env")
    print("2. Set SENTRY_DSN=your-sentry-dsn in .env")
    print()
    print("For testing without a real Sentry account:")
    print("You can use a mock DSN or create a free account at https://sentry.io")
    print()
else:
    print("✅ Sentry is ENABLED")
    print(f"   Environment: {settings.sentry_environment}")
    print(f"   DSN: {settings.sentry_dsn[:50]}...")
    print()

print("Running Sentry tests (events will be sent if enabled)...")
print()

# Test 1: Capture Message
print("1. Testing capture_message...")
capture_message(
    "Test message from Sentry integration test",
    level="info",
    test_context={"test_id": 123, "test_type": "integration"},
)
print("   ✅ Message captured")
print()

# Test 2: Set User Context
print("2. Testing user context...")
set_user_context(user_id=456, username="test_user", email="test@example.com", role="admin")
print("   ✅ User context set")
print()

# Test 3: Add Breadcrumbs
print("3. Testing breadcrumbs...")
add_breadcrumb("User logged in", category="auth", level="info", user_id=456)
add_breadcrumb("Navigated to dashboard", category="navigation", level="info")
add_breadcrumb("Started data export", category="action", level="info")
print("   ✅ Breadcrumbs added")
print()

# Test 4: Custom Context
print("4. Testing custom context...")
set_context(
    "scraping_job", {"job_id": 789, "source": "gelbe_seiten", "city": "Stuttgart", "industry": "IT"}
)
print("   ✅ Custom context set")
print()

# Test 5: Capture Exception
print("5. Testing exception capture...")
try:
    # Simulate an error
    result = 1 / 0
except ZeroDivisionError as e:
    capture_exception(e, operation="test_division", numerator=1, denominator=0)
    print("   ✅ Exception captured")
print()

# Test 6: Performance Transaction
print("6. Testing performance transaction...")
with start_transaction(name="test_scraping_job", op="scraping") as transaction:
    # Simulate some work
    import time

    # Child span 1
    with transaction.start_child(op="http", description="Fetch page") as span:
        time.sleep(0.1)

    # Child span 2
    with transaction.start_child(op="db", description="Save results") as span:
        time.sleep(0.05)

    # Child span 3
    with transaction.start_child(op="processing", description="Process data") as span:
        time.sleep(0.08)

print("   ✅ Transaction completed")
print()

# Test 7: Nested Exception with Context
print("7. Testing nested exception with full context...")
try:
    set_context(
        "database",
        {
            "operation": "INSERT",
            "table": "companies",
            "connection": "postgresql://localhost:5432/kr_leads",
        },
    )

    add_breadcrumb("Starting database operation", category="db", level="info")
    add_breadcrumb("Validating data", category="db", level="info")
    add_breadcrumb("Executing query", category="db", level="warning")

    # Simulate database error
    raise Exception("Database connection timeout after 30 seconds")

except Exception as e:
    capture_exception(
        e, query="INSERT INTO companies VALUES (...)", retry_count=3, timeout_seconds=30
    )
    print("   ✅ Nested exception captured with context")
print()

print("=" * 60)
print("✅ All Sentry tests completed!")
print("=" * 60)
print()

if settings.sentry_enabled:
    print("🔍 Check your Sentry dashboard to see the captured events:")
    print(f"   Environment: {settings.sentry_environment}")
    print()
    print("You should see:")
    print("  - 1 info message")
    print("  - 2 exceptions (ZeroDivisionError, Database timeout)")
    print("  - 1 performance transaction with 3 spans")
    print("  - User context (test_user)")
    print("  - Custom contexts (scraping_job, database)")
    print("  - Multiple breadcrumbs")
else:
    print("ℹ️  Sentry is disabled - no events were sent")
    print("   Enable Sentry to see events in your dashboard")

print()
