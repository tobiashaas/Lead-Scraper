#!/bin/bash

set -euo pipefail

# Comprehensive Health Check Script for KR Lead Scraper
# Usage: ./health_check.sh <environment> [--verbose]

ENVIRONMENT="${1:-}"
VERBOSE="false"
if [ "${2:-}" = "--verbose" ]; then
  VERBOSE="true"
fi

if [ -z "$ENVIRONMENT" ]; then
  echo "Usage: $0 <environment> [--verbose]"
  exit 1
fi

case "$ENVIRONMENT" in
  production)
    API_URL="https://api.your-domain.com"
    ;;
  staging)
    API_URL="https://staging.your-domain.com"
    ;;
  *)
    echo "Unsupported environment: $ENVIRONMENT"
    exit 1
    ;;
esac

DEPLOYMENT_DIR="/opt/kr-scraper"
if [ "$ENVIRONMENT" = "staging" ]; then
  DEPLOYMENT_DIR="/opt/kr-scraper-staging"
fi

LOG_DIR="${DEPLOYMENT_DIR}/logs"
mkdir -p "$LOG_DIR"

MAX_RETRIES=10
RETRY_INTERVAL=30
TIMEOUT=10
RESULTS=()

log() {
  local message="$1"
  if [ "$VERBOSE" = "true" ]; then
    echo "$message"
  fi
}

record_result() {
  local name="$1"
  local status="$2"
  local detail="$3"
  RESULTS+=("$name|$status|$detail")
}

check_api_health() {
  log "Checking API health endpoint..."
  if RESPONSE=$(curl -fsS --max-time "$TIMEOUT" "$API_URL/health"); then
    if echo "$RESPONSE" | jq -e '.status == "healthy"' >/dev/null 2>&1; then
      record_result "api_health" "pass" "Health endpoint healthy"
      return 0
    fi
  fi
  record_result "api_health" "fail" "Health endpoint check failed"
  return 1
}

check_api_detailed_health() {
  log "Checking detailed health endpoint..."
  if RESPONSE=$(curl -fsS --max-time "$TIMEOUT" "$API_URL/health/detailed"); then
    if echo "$RESPONSE" | jq -e '.status == "healthy" and .database.status == "healthy" and .redis.status == "healthy"' >/dev/null 2>&1; then
      record_result "api_detailed_health" "pass" "Detailed health healthy"
      return 0
    fi
    record_result "api_detailed_health" "fail" "Detailed health not healthy: $RESPONSE"
    return 1
  fi
  record_result "api_detailed_health" "fail" "Failed to reach detailed health endpoint"
  return 1
}

check_api_docs() {
  log "Checking docs endpoint..."
  if curl -fsS --max-time "$TIMEOUT" "$API_URL/docs" >/dev/null; then
    record_result "api_docs" "pass" "Docs accessible"
    return 0
  fi
  record_result "api_docs" "fail" "Docs endpoint unavailable"
  return 1
}

check_container_health() {
  local container="kr-app-prod"
  if [ "$ENVIRONMENT" = "staging" ]; then
    container="kr-app-staging"
  fi
  log "Inspecting container health for $container"
  if STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null); then
    if [ "$STATUS" = "healthy" ]; then
      record_result "container_health" "pass" "Container healthy"
      return 0
    fi
    record_result "container_health" "fail" "Container health status: $STATUS"
    return 1
  fi
  record_result "container_health" "fail" "Container not found"
  return 1
}

check_database_connectivity() {
  log "Checking database connectivity..."
  local container="kr-app-prod"
  if [ "$ENVIRONMENT" = "staging" ]; then
    container="kr-app-staging"
  fi
  if docker exec "$container" python -c "from app.database.database import engine; conn = engine.connect(); conn.close()" >/dev/null 2>&1; then
    record_result "database" "pass" "Database connection successful"
    return 0
  fi
  record_result "database" "fail" "Database connectivity failed"
  return 1
}

check_redis_connectivity() {
  log "Checking redis connectivity..."
  local container="kr-app-prod"
  if [ "$ENVIRONMENT" = "staging" ]; then
    container="kr-app-staging"
  fi
  if docker exec "$container" python -c "from app.core.config import settings; import redis; redis.from_url(settings.redis_url).ping()" >/dev/null 2>&1; then
    record_result "redis" "pass" "Redis connection successful"
    return 0
  fi
  record_result "redis" "fail" "Redis connectivity failed"
  return 1
}

check_secrets_manager() {
  log "Checking secrets manager logs..."
  local container="kr-app-prod"
  if [ "$ENVIRONMENT" = "staging" ]; then
    container="kr-app-staging"
  fi
  if docker logs "$container" 2>&1 | grep -q "Loaded secrets from"; then
    record_result "secrets" "pass" "Secrets manager reported"
    return 0
  fi
  record_result "secrets" "warn" "Secrets manager confirmation missing"
  return 0
}

check_authentication() {
  log "Performing authentication flow..."
  if [ -z "${SMOKE_TEST_PASSWORD:-}" ]; then
    record_result "authentication" "skip" "SMOKE_TEST_PASSWORD not set"
    return 0
  fi
  local payload='{"username":"staging_bot","password":"'$SMOKE_TEST_PASSWORD'"}'
  if RESPONSE=$(curl -fsS -X POST -H "Content-Type: application/json" -d "$payload" "$API_URL/api/v1/auth/login"); then
    TOKEN=$(echo "$RESPONSE" | jq -r '.access_token')
    if [ -n "$TOKEN" ] && [ "$TOKEN" != "null" ]; then
      if curl -fsSH "Authorization: Bearer $TOKEN" "$API_URL/api/v1/companies" >/dev/null; then
        record_result "authentication" "pass" "Authentication flow succeeded"
        return 0
      fi
    fi
  fi
  record_result "authentication" "fail" "Authentication flow failed"
  return 1
}

check_critical_endpoints() {
  log "Checking critical endpoints..."
  local failures=0
  for endpoint in "/api/v1/companies" "/api/v1/scraping/sources" "/health/detailed"; do
    if curl -fsS "$API_URL$endpoint" >/dev/null; then
      log "Endpoint $endpoint healthy"
    else
      failures=$((failures + 1))
      log "Endpoint $endpoint failed"
    fi
  done
  if [ "$failures" -eq 0 ]; then
    record_result "critical_endpoints" "pass" "All critical endpoints reachable"
    return 0
  fi
  record_result "critical_endpoints" "fail" "$failures critical endpoints unreachable"
  return 1
}

run_smoke_tests() {
  local failures=0
  check_container_health || failures=$((failures + 1))
  check_api_health || failures=$((failures + 1))
  check_api_detailed_health || failures=$((failures + 1))
  check_database_connectivity || failures=$((failures + 1))
  check_redis_connectivity || failures=$((failures + 1))
  check_secrets_manager || true
  check_api_docs || failures=$((failures + 1))
  check_authentication || failures=$((failures + 1))
  check_critical_endpoints || failures=$((failures + 1))
  return "$failures"
}

retry_health_checks() {
  local attempt=1
  while [ "$attempt" -le "$MAX_RETRIES" ]; do
    log "Health check iteration $attempt/$MAX_RETRIES"
    FAILURES=$(run_smoke_tests) || FAILURES=$?
    if [ "$FAILURES" -eq 0 ]; then
      return 0
    fi
    if [ "$attempt" -eq "$MAX_RETRIES" ]; then
      return 1
    fi
    log "Retrying in ${RETRY_INTERVAL}s..."
    sleep "$RETRY_INTERVAL"
    RESULTS=()
    attempt=$((attempt + 1))
  done
}

generate_report() {
  local report_file="${LOG_DIR}/health_report_$(date +%Y%m%d_%H%M%S).json"
  {
    echo '{'
    echo "  \"timestamp\": \"$(date -Iseconds)\"," 
    echo "  \"environment\": \"${ENVIRONMENT}\"," 
    echo '  "checks": ['
    local first=true
    for result in "${RESULTS[@]}"; do
      IFS='|' read -r name status detail <<<"$result"
      if [ "$first" = true ]; then
        first=false
      else
        echo ','
      fi
      printf '    {"name": "%s", "status": "%s", "detail": "%s"}' "$name" "$status" "$detail"
    done
    echo
    echo '  ]'
    echo '}'
  } > "$report_file"
  echo "Health report saved to $report_file"
}

main() {
  log "Starting health checks for $ENVIRONMENT at $API_URL"
  if retry_health_checks; then
    echo "✅ Health checks passed for $ENVIRONMENT"
    generate_report
    exit 0
  else
    echo "❌ Health checks failed for $ENVIRONMENT"
    generate_report
    exit 1
  fi
}

main
