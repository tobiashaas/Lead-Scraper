# Testing Guide

This document provides a comprehensive guide to testing in the Lead-Scraper project.

## Test Structure and Organization

The test suite is organized as follows:

```
tests/
├── integration/           # Integration tests for API endpoints
│   ├── test_api_auth.py    # Authentication tests
│   ├── test_api_companies.py  # Company-related tests
│   ├── test_api_scraping.py   # Scraping job tests
│   ├── test_api_bulk.py       # Bulk operation tests
│   ├── test_api_export.py     # Export functionality tests
│   ├── test_api_webhooks.py   # Webhook tests
│   └── test_api_health.py     # Health check tests
├── unit/                  # Unit tests for individual components
│   ├── test_models.py     # Database model tests
│   └── test_services.py   # Service layer tests
└── utils/                 # Test utilities and helpers
    └── test_helpers.py    # Reusable test functions
```

## Running Tests

### Prerequisites

- Python 3.8+
- All project dependencies installed (`pip install -r requirements.txt`)
- Test dependencies installed (`pip install -r requirements-test.txt`)

### Running All Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=app/api --cov-report=term-missing
```

### Running Specific Test Categories

```bash
# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run tests with a specific marker
pytest -m "not slow"  # Skip slow tests
pytest -m "security"  # Run only security tests
pytest -m "performance"  # Run only performance tests
```

### Using Helper Scripts

We provide helper scripts in the `scripts/` directory:

```bash
# Run tests with coverage and generate HTML report
./scripts/run_coverage.sh --html

# Run integration tests with parallel execution and coverage
./scripts/run_integration_tests.sh --parallel --coverage

# Run specific test markers
./scripts/run_integration_tests.sh --markers "security and not slow"
```

## Test Coverage

We aim for at least 80% test coverage for all API endpoints. To generate a coverage report:

```bash
# Generate HTML coverage report
pytest --cov=app/api --cov-report=html

# Open the report in your default browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov\\index.html  # Windows
```

## Writing Tests

### Test Naming Conventions

- Test files: `test_*.py`
- Test classes: `Test*` (e.g., `TestAuthentication`)
- Test methods: `test_*` (e.g., `test_login_success`)

### Test Structure

Each test file should follow this structure:

```python
import pytest
from fastapi.testclient import TestClient

class TestFeature:
    def test_feature_behavior(self, client: TestClient):
        # Arrange
        # Set up test data
        
        # Act
        response = client.get("/api/endpoint")
        
        # Assert
        assert response.status_code == 200
        assert response.json()["key"] == "expected_value"
```

### Using Fixtures

We provide several fixtures in `tests/conftest.py`:

- `client`: TestClient instance
- `db_session`: Database session with automatic rollback
- `auth_headers`: Authentication headers for test user
- `admin_user`: Admin user fixture
- `test_user`: Regular user fixture

### Best Practices

1. **Test Isolation**: Each test should be independent and not rely on state from other tests.
2. **Descriptive Names**: Test names should clearly describe what they're testing.
3. **Arrange-Act-Assert**: Follow the AAA pattern for test structure.
4. **Minimal Fixtures**: Only set up the data needed for each test.
5. **Clean Up**: Use teardown or fixture finalizers to clean up test data.

## Performance Testing

We include performance tests to ensure the API remains responsive. These tests are marked with `@pytest.mark.performance`.

```bash
# Run performance tests
pytest -m performance

# Run performance tests with timing
pytest -m performance -v --durations=10
```

## Security Testing

Security tests help identify vulnerabilities. These tests are marked with `@pytest.mark.security`.

```bash
# Run security tests
pytest -m security
```

## CI/CD Integration

Tests are automatically run on every push and pull request via GitHub Actions. The CI pipeline:

1. Runs all tests with coverage
2. Fails if coverage is below 80%
3. Uploads test results as artifacts
4. Updates the coverage badge

## Troubleshooting

### Common Issues

1. **Database Connection Errors**:
   - Ensure the test database is properly set up
   - Check database connection strings in test environment

2. **Test Failures**:
   - Run tests with `-v` for verbose output
   - Check for database state issues (use `--pdb` to debug)

3. **Slow Tests**:
   - Mark slow tests with `@pytest.mark.slow`
   - Run without slow tests: `pytest -m "not slow"`

4. **Flaky Tests**:
   - Ensure tests are properly isolated
   - Use `pytest-rerunfailures` for known flaky tests

### Debugging

To debug a failing test:

```bash
# Run a specific test with debugger
pytest tests/integration/test_api.py::TestFeature::test_something --pdb

# Show all print statements
pytest -s

# Show warnings
pytest -r w
```

## Code Style

- Follow PEP 8
- Use type hints
- Keep test functions focused on a single behavior
- Use descriptive assertion messages

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing Guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [pytest-xdist Documentation](https://pytest-xdist.readthedocs.io/)
