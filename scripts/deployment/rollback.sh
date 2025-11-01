#!/bin/bash

set -euo pipefail

# Automated Rollback Script for KR Lead Scraper
# Usage: ./rollback.sh <target_version> <environment> [--restore-db] [--force] [--verbose]

TARGET_VERSION="${1:-}"
ENVIRONMENT="${2:-}"
RESTORE_DB="false"
FORCE="false"
VERBOSE="false"
shift 2 || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --restore-db)
      RESTORE_DB="true"
      ;;
    --force)
      FORCE="true"
      ;;
    --verbose)
      VERBOSE="true"
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
  shift
done

if [ -z "$TARGET_VERSION" ] || [ -z "$ENVIRONMENT" ]; then
  echo "Usage: $0 <target_version> <environment> [--restore-db] [--force] [--verbose]"
  exit 1
fi

case "$ENVIRONMENT" in
  production|staging)
    ;;
  *)
    echo "Unsupported environment: $ENVIRONMENT"
    exit 1
    ;;
esac

DOCKER_REGISTRY="ghcr.io"
IMAGE_NAME="${IMAGE_NAME:-tobiashaas/lead-scraper}"
if [ "$ENVIRONMENT" = "production" ]; then
  COMPOSE_FILE="docker-compose.prod.yml"
  CONTAINER_NAME="kr-app-prod"
  POSTGRES_CONTAINER="kr-postgres-prod"
else
  COMPOSE_FILE="docker-compose.staging.yml"
  CONTAINER_NAME="kr-app-staging"
  POSTGRES_CONTAINER="kr-postgres-staging"
fi
BACKUP_DIR="/opt/kr-scraper/backups"
if [ "$ENVIRONMENT" = "staging" ]; then
  BACKUP_DIR="/opt/kr-scraper-staging/backups"
fi
LOG_DIR="/opt/kr-scraper/logs"
if [ "$ENVIRONMENT" = "staging" ]; then
  LOG_DIR="/opt/kr-scraper-staging/logs"
fi
LOG_FILE="${LOG_DIR}/rollback.log"

mkdir -p "$BACKUP_DIR" "$LOG_DIR"

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  local message="$1"
  local ts
  ts=$(timestamp)
  echo "[$ts] $message" | tee -a "$LOG_FILE"
}

if [ "$VERBOSE" = "true" ]; then
  set -x
fi

get_current_version() {
  CURRENT_VERSION=$(docker inspect --format='{{index .Config.Labels "com.kr-scraper.version"}}' "$CONTAINER_NAME" 2>/dev/null || echo "unknown")
  if [ -z "$CURRENT_VERSION" ] || [ "$CURRENT_VERSION" = "<no value>" ]; then
    CURRENT_VERSION=$(docker inspect --format='{{index .Config.Labels "version"}}' "$CONTAINER_NAME" 2>/dev/null || echo "unknown")
  fi
  log "Current deployed version: $CURRENT_VERSION"
}

normalize_target_tag() {
  if [[ "$TARGET_VERSION" =~ ^v ]]; then
    TARGET_VERSION="${TARGET_VERSION#v}"
  fi
  if [[ "$TARGET_VERSION" =~ ^staging- ]]; then
    TARGET_TAG="$TARGET_VERSION"
  else
    TARGET_TAG="v${TARGET_VERSION}"
  fi
  log "Target version tag: $TARGET_TAG"
}

validate_target_version() {
  log "Validating target version $TARGET_VERSION"
  if ! docker manifest inspect "${DOCKER_REGISTRY}/${IMAGE_NAME}:${TARGET_TAG}" >/dev/null 2>&1; then
    log "ERROR: Target image ${TARGET_TAG} not found in registry"
    exit 1
  fi
  if [ "$CURRENT_VERSION" != "unknown" ] && [ "$CURRENT_VERSION" = "$TARGET_VERSION" ]; then
    log "ERROR: Target version equals current version"
    exit 1
  fi
}

find_latest_backup() {
  LATEST_BACKUP=$(ls -t "${BACKUP_DIR}"/db_backup_*.sql 2>/dev/null | head -n 1 || true)
  if [ -n "$LATEST_BACKUP" ]; then
    log "Latest DB backup: $LATEST_BACKUP"
  else
    log "No database backup found"
  fi
}

confirm_rollback() {
  if [ "$FORCE" = "true" ]; then
    return
  fi
  echo "Rollback from ${CURRENT_VERSION} to ${TARGET_VERSION}. Continue? (yes/no)"
  read -r answer
  if [ "$answer" != "yes" ]; then
    log "Rollback aborted by user"
    exit 0
  fi
}

stop_current_container() {
  if docker ps --format '{{.Names}}' | grep -q "$CONTAINER_NAME"; then
    log "Stopping current container $CONTAINER_NAME"
    docker stop --time=30 "$CONTAINER_NAME" || true
  else
    log "Current container not running"
  fi
}

restore_database_backup() {
  if [ "$RESTORE_DB" != "true" ]; then
    return
  fi
  if [ -z "$LATEST_BACKUP" ]; then
    log "ERROR: No database backup available for restore"
    exit 1
  fi

  local db_name="kr_leads"
  local db_user="kr_user"
  if [ "$ENVIRONMENT" = "staging" ]; then
    db_name="kr_leads_staging"
    db_user="kr_user_staging"
  fi

  log "Restoring database from $LATEST_BACKUP"
  cat "$LATEST_BACKUP" | docker exec -i "$POSTGRES_CONTAINER" psql -U "$db_user" "$db_name"
}

pull_target_image() {
  log "Pulling target image ${DOCKER_REGISTRY}/${IMAGE_NAME}:${TARGET_TAG}"
  docker pull "${DOCKER_REGISTRY}/${IMAGE_NAME}:${TARGET_TAG}"
}

start_target_container() {
  export VERSION="$TARGET_VERSION"
  export IMAGE_REF="${DOCKER_REGISTRY}/${IMAGE_NAME}:${TARGET_TAG}"
  log "Starting container $CONTAINER_NAME with image ${TARGET_TAG}"
  if [ "$ENVIRONMENT" = "production" ]; then
    # For production, determine which blue/green container to start
    local target_service="app-blue"
    docker-compose -f "$COMPOSE_FILE" up -d --no-deps "$target_service"
  else
    docker-compose -f "$COMPOSE_FILE" up -d --no-deps app
  fi

  local timeout=60
  local elapsed=0
  while [ "$elapsed" -lt "$timeout" ]; do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "starting")
    if [ "$STATUS" = "healthy" ]; then
      log "Container $CONTAINER_NAME is healthy"
      return
    fi
    sleep 5
    elapsed=$((elapsed + 5))
  done
  log "ERROR: Container failed to reach healthy state"
  exit 1
}

verify_rollback() {
  log "Running health check script"
  ./health_check.sh "$ENVIRONMENT" --verbose

  DEPLOYED_VERSION=$(docker inspect --format='{{index .Config.Labels "com.kr-scraper.version"}}' "$CONTAINER_NAME" 2>/dev/null || echo "unknown")
  if [ -z "$DEPLOYED_VERSION" ] || [ "$DEPLOYED_VERSION" = "<no value>" ]; then
    DEPLOYED_VERSION=$(docker inspect --format='{{index .Config.Labels "version"}}' "$CONTAINER_NAME" 2>/dev/null || echo "unknown")
  fi
  log "Deployed version after rollback: $DEPLOYED_VERSION"
  if [ "$DEPLOYED_VERSION" != "$TARGET_VERSION" ]; then
    log "ERROR: Version mismatch after rollback"
    exit 1
  fi
}

create_incident_report() {
  local report_file="${BACKUP_DIR}/incident_report_$(date +%Y%m%d_%H%M%S).json"
  {
    echo '{'
    echo "  \"timestamp\": \"$(date -Iseconds)\"," 
    echo "  \"environment\": \"${ENVIRONMENT}\"," 
    echo "  \"rolled_from\": \"${CURRENT_VERSION}\"," 
    echo "  \"rolled_to\": \"${TARGET_VERSION}\"," 
    echo "  \"image_tag\": \"${TARGET_TAG}\"," 
    echo "  \"restore_db\": ${RESTORE_DB},"
    echo "  \"backup_used\": \"${LATEST_BACKUP:-none}\""
    echo '}'
  } > "$report_file"
  log "Incident report saved to $report_file"
}

main() {
  log "Initiating rollback to version ${TARGET_VERSION} in ${ENVIRONMENT}"
  get_current_version
  normalize_target_tag
  validate_target_version
  find_latest_backup
  confirm_rollback
  stop_current_container
  if [ "$RESTORE_DB" = "true" ]; then
    restore_database_backup
  fi
  pull_target_image
  start_target_container
  verify_rollback
  create_incident_report
  log "Rollback to version ${TARGET_VERSION} completed successfully"
}

main "$@"
