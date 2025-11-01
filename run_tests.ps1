# PowerShell script to run tests with SQLite database

# Set environment variable for SQLite test database
$env:DATABASE_URL = "sqlite:///./test.db"
$env:ENVIRONMENT = "test"

# Run pytest with the specified arguments
if ($args.Count -gt 0) {
    python -m pytest @args
} else {
    python -m pytest tests/unit/ -v --no-cov
}

# Display exit code
Write-Host "`nTest execution completed with exit code: $LASTEXITCODE"
