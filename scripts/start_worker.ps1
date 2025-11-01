# Start RQ worker for local development (Windows)

Write-Host "Starting RQ worker for scraping queue..." -ForegroundColor Green
$redisUrl = if ($env:REDIS_URL) { $env:REDIS_URL } else { "redis://localhost:6379" }
Write-Host ("Redis URL: {0}" -f $redisUrl) -ForegroundColor Cyan
Write-Host ""

# Activate virtual environment if it exists
if (Test-Path "venv\Scripts\Activate.ps1") {
    & .\venv\Scripts\Activate.ps1
}

# Ensure PYTHONPATH includes project root
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = ("{0};{1}" -f (Get-Location), $env:PYTHONPATH)
} else {
    $env:PYTHONPATH = (Get-Location)
}

# Initialize scheduled jobs
Write-Host "Initializing scheduled jobs..." -ForegroundColor Cyan
try {
    python -c "from app.workers.queue import initialize_scheduled_jobs; initialize_scheduled_jobs()"
} catch {
    Write-Host "Warning: Failed to initialize scheduled jobs" -ForegroundColor Yellow
}

rq worker scraping maintenance `
    --url $redisUrl `
    --with-scheduler `
    --verbose
