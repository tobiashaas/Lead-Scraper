#!/bin/bash
# Start RQ worker for local development

set -euo pipefail

echo "Starting RQ worker for scraping queue..."
echo "Redis URL: ${REDIS_URL:-redis://localhost:6379}"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
fi

# Ensure PYTHONPATH includes project root
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"

# Initialize scheduled jobs
echo "Initializing scheduled jobs..."
python -c "from app.workers.queue import initialize_scheduled_jobs; initialize_scheduled_jobs()" || echo "Warning: Failed to initialize scheduled jobs"

rq worker scraping maintenance \
    --url "${REDIS_URL:-redis://localhost:6379}" \
    --with-scheduler \
    --verbose
