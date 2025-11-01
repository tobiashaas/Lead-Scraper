#!/bin/bash

set -euo pipefail

# Blue-Green Deployment Script for KR Lead Scraper
# Usage: ./deploy.sh <version> <environment>
# Example: ./deploy.sh 1.2.3 production

VERSION="${1:-}"
ENVIRONMENT="${2:-}"

if [ -z "$VERSION" ] || [ -z "$ENVIRONMENT" ]; then
  echo "Usage: $0 <version> <environment>"
  echo "Example: $0 1.2.3 production"
  exit 1
fi

DOCKER_REGISTRY="ghcr.io"
IMAGE_NAME="${IMAGE_NAME:-tobiashaas/lead-scraper}"
if [ "$ENVIRONMENT" = "production" ]; then
  COMPOSE_FILE="docker-compose.prod.yml"
  CONTAINER_PREFIX="kr-app-prod"
else
  COMPOSE_FILE="docker-compose.staging.yml"
  CONTAINER_PREFIX="kr-app-staging"
fi
CONTAINER_NAME="${CONTAINER_PREFIX}"
BLUE_CONTAINER="${CONTAINER_PREFIX}-blue"
GREEN_CONTAINER="${CONTAINER_PREFIX}-green"
DEPLOYMENT_DIR="/opt/kr-scraper"
BACKUP_DIR="${DEPLOYMENT_DIR}/backups"
LOG_DIR="${DEPLOYMENT_DIR}/logs"
LOG_FILE="${LOG_DIR}/deployment.log"

CURRENT_CONTAINER=""
TARGET_CONTAINER=""
ROLLBACK_TRIGGERED="false"

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

error() {
  local message="$1"
  log "ERROR: $message"
}

check_prerequisites() {
  log "Checking prerequisites..."

  if ! command -v docker >/dev/null 2>&1; then
    error "Docker is not installed."
    exit 1
  fi

  if ! command -v docker-compose >/dev/null 2>&1; then
    error "docker-compose is not installed."
    exit 1
  fi

  if [ ! -f "$COMPOSE_FILE" ]; then
    error "Compose file $COMPOSE_FILE not found."
    exit 1
  fi

  if [ ! -f ".env.${ENVIRONMENT}" ]; then
    error ".env.${ENVIRONMENT} file not found."
    exit 1
  fi

  log "All prerequisites satisfied."
}

get_current_container() {
  CURRENT_CONTAINER=$(docker ps --filter "name=${CONTAINER_NAME}" --filter "status=running" --format '{{.Names}}' | head -n 1 || true)
  if [ -z "$CURRENT_CONTAINER" ]; then
    log "No active container found for ${CONTAINER_NAME}. Defaulting to blue deployment."
    CURRENT_CONTAINER="$GREEN_CONTAINER"
  else
    log "Current active container: $CURRENT_CONTAINER"
  fi
}

determine_target_container() {
  if [[ "$CURRENT_CONTAINER" == *"blue" ]]; then
    TARGET_CONTAINER="$GREEN_CONTAINER"
  else
    TARGET_CONTAINER="$BLUE_CONTAINER"
  fi
  log "Target container for deployment: $TARGET_CONTAINER"
}

login_to_ghcr() {
  log "Logging in to GitHub Container Registry..."
  if [ -n "${GHCR_PAT:-}" ]; then
    echo "$GHCR_PAT" | docker login ghcr.io -u "${GHCR_USER:-tobiashaas}" --password-stdin
  else
    log "GHCR_PAT not set, assuming already logged in or public image"
  fi
}

pull_new_image() {
  local retries=3
  local attempt=1
  local image_tag

  if [[ "$VERSION" =~ ^staging- ]]; then
    image_tag="$VERSION"
  else
    image_tag="v${VERSION}"
  fi

  export IMAGE_REF="${DOCKER_REGISTRY}/${IMAGE_NAME}:${image_tag}"
  log "Pulling image ${IMAGE_REF}"

  until docker pull "${IMAGE_REF}"; do
    if [ "$attempt" -ge "$retries" ]; then
      error "Failed to pull image after $retries attempts."
      return 1
    fi
    attempt=$((attempt + 1))
    sleep $((attempt * 5))
  done

  log "Image ${image_tag} pulled successfully."
}

backup_current_state() {
  local backup_timestamp
  backup_timestamp=$(date +%Y%m%d_%H%M%S)

  log "Creating backups (timestamp: $backup_timestamp)..."

  cp "${COMPOSE_FILE}" "${BACKUP_DIR}/compose_backup_${backup_timestamp}.yml"
  cp ".env.${ENVIRONMENT}" "${BACKUP_DIR}/env_backup_${backup_timestamp}"

  local db_container="kr-postgres-prod"
  local db_name="kr_leads"
  local db_user="kr_user"

  if [ "$ENVIRONMENT" = "staging" ]; then
    db_container="kr-postgres-staging"
    db_name="kr_leads_staging"
    db_user="kr_user_staging"
  fi

  if docker ps --format '{{.Names}}' | grep -q "$db_container"; then
    log "Backing up database ($db_container)..."
    if ! docker exec "$db_container" pg_dump -U "$db_user" "$db_name" | gzip > "${BACKUP_DIR}/db_backup_${backup_timestamp}.sql.gz"; then
      error "Database backup failed."
      return 1
    fi
  else
    log "Database container $db_container not running. Skipping DB backup."
  fi

  log "Backups created at ${BACKUP_DIR}."
}

start_new_container() {
  log "Starting new container: $TARGET_CONTAINER"

  export VERSION="$VERSION"
  export IMAGE_REF="${IMAGE_REF}"

  if [ "$ENVIRONMENT" = "production" ]; then
    if [[ "$TARGET_CONTAINER" == *"blue" ]]; then
      docker-compose -f "$COMPOSE_FILE" up -d --no-deps app-blue
    else
      docker-compose -f "$COMPOSE_FILE" up -d --no-deps app-green
    fi
  else
    docker-compose -f "$COMPOSE_FILE" up -d --no-deps app
  fi

  local timeout=30
  local elapsed=0
  while [ "$elapsed" -lt "$timeout" ]; do
    local status
    status=$(docker inspect --format='{{.State.Health.Status}}' "$TARGET_CONTAINER" 2>/dev/null || echo "starting")
    if [ "$status" = "healthy" ]; then
      log "Container $TARGET_CONTAINER is healthy."
      return 0
    fi
    sleep 5
    elapsed=$((elapsed + 5))
  done

  error "Container $TARGET_CONTAINER failed to become healthy."
  return 1
}

run_health_checks() {
  log "Running health checks on $TARGET_CONTAINER"

  local container_ip
  container_ip=$(docker inspect --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$TARGET_CONTAINER")

  if [ -z "$container_ip" ]; then
    error "Unable to determine container IP for $TARGET_CONTAINER"
    return 1
  fi

  local retries=10
  local interval=30
  local attempt=1

  while [ "$attempt" -le "$retries" ]; do
    log "Health check attempt ${attempt}/${retries}"

    if curl -fs "http://${container_ip}:8000/health" >/tmp/health.json && \
       curl -fs "http://${container_ip}:8000/health/detailed" >/tmp/health_detailed.json; then
      if jq -e '.status == "healthy"' /tmp/health.json >/dev/null && \
         jq -e '.status == "healthy"' /tmp/health_detailed.json >/dev/null; then
        log "API health endpoints returned healthy status."

        if docker exec "$TARGET_CONTAINER" python -c "from app.database.database import engine; engine.connect()" >/dev/null 2>&1; then
          log "Database connectivity check succeeded."
        else
          error "Database connectivity check failed."
          return 1
        fi

        if docker exec "$TARGET_CONTAINER" python -c "from app.core.config import settings; import redis; redis.from_url(settings.redis_url).ping()" >/dev/null 2>&1; then
          log "Redis connectivity check succeeded."
        else
          error "Redis connectivity check failed."
          return 1
        fi

        log "All health checks passed."
        return 0
      fi
    fi

    if [ "$attempt" -eq "$retries" ]; then
      error "Health checks failed after ${retries} attempts."
      return 1
    fi

    log "Waiting ${interval}s before retry..."
    sleep "$interval"
    attempt=$((attempt + 1))
  done
}

switch_traffic() {
  log "Switching traffic to $TARGET_CONTAINER"

  if [ "$ENVIRONMENT" = "production" ]; then
    # Determine active color from target container
    local active_color
    if [[ "$TARGET_CONTAINER" == *"blue" ]]; then
      active_color="blue"
    else
      active_color="green"
    fi
    
    log "Switching nginx upstream to ${active_color}..."
    
    # Update the symlink inside the nginx container to point to the active upstream
    docker exec kr-nginx-prod ln -sf /etc/nginx/conf.d/upstream-${active_color}.conf /etc/nginx/conf.d/upstream-active.conf
    
    # Verify the symlink points to the correct file
    local symlink_target
    symlink_target=$(docker exec kr-nginx-prod readlink /etc/nginx/conf.d/upstream-active.conf)
    if [[ "$symlink_target" != "/etc/nginx/conf.d/upstream-${active_color}.conf" ]]; then
      error "Symlink verification failed. Expected /etc/nginx/conf.d/upstream-${active_color}.conf, got ${symlink_target}"
      return 1
    fi
    log "Symlink verified: upstream-active.conf -> upstream-${active_color}.conf"
    
    # Reload nginx to apply the new upstream configuration
    if ! docker exec kr-nginx-prod nginx -s reload; then
      error "Nginx reload failed"
      return 1
    fi
    log "Nginx reloaded successfully"
    
    # Mark containers with active label for observability
    if [ -n "$CURRENT_CONTAINER" ] && docker ps --format '{{.Names}}' | grep -q "$CURRENT_CONTAINER"; then
      docker update --label-add com.kr-scraper.active=false "$CURRENT_CONTAINER" || true
    fi
    docker update --label-add com.kr-scraper.active=true "$TARGET_CONTAINER" || true
  else
    docker update --label-add com.kr-scraper.active=true "$TARGET_CONTAINER" || true
  fi

  log "Traffic switched to $TARGET_CONTAINER."
}

stop_old_container() {
  if [ -z "$CURRENT_CONTAINER" ]; then
    log "No previous container to stop."
    return
  fi

  if docker ps --format '{{.Names}}' | grep -q "$CURRENT_CONTAINER"; then
    log "Stopping old container $CURRENT_CONTAINER"
    docker stop --time=30 "$CURRENT_CONTAINER" || true
    docker rm "$CURRENT_CONTAINER" || true
  else
    log "Old container $CURRENT_CONTAINER not running."
  fi
}

cleanup_old_images() {
  log "Cleaning up old Docker images"
  local images
  images=$(docker images "${DOCKER_REGISTRY}/${IMAGE_NAME}" --format '{{.Tag}}' | sort -V | head -n -3 || true)
  if [ -n "$images" ]; then
    echo "$images" | xargs -r -n 1 docker rmi || true
  fi
}

rollback() {
  if [ "$ROLLBACK_TRIGGERED" = "true" ]; then
    return
  fi
  ROLLBACK_TRIGGERED="true"

  error "Deployment failed. Rolling back to $CURRENT_CONTAINER"

  if [ -n "$TARGET_CONTAINER" ]; then
    docker stop "$TARGET_CONTAINER" || true
    docker rm "$TARGET_CONTAINER" || true
  fi

  if [ -n "$CURRENT_CONTAINER" ]; then
    if ! docker ps --format '{{.Names}}' | grep -q "$CURRENT_CONTAINER"; then
      docker-compose -f "$COMPOSE_FILE" up -d "$CURRENT_CONTAINER"
    else
      docker start "$CURRENT_CONTAINER" || true
    fi
    docker update --label-add com.kr-scraper.active=true "$CURRENT_CONTAINER" || true
    
    # Rollback nginx upstream symlink if in production
    if [ "$ENVIRONMENT" = "production" ]; then
      local rollback_color
      if [[ "$CURRENT_CONTAINER" == *"blue" ]]; then
        rollback_color="blue"
      else
        rollback_color="green"
      fi
      log "Rolling back nginx upstream to ${rollback_color}..."
      docker exec kr-nginx-prod ln -sf /etc/nginx/conf.d/upstream-${rollback_color}.conf /etc/nginx/conf.d/upstream-active.conf || true
      docker exec kr-nginx-prod nginx -s reload || true
    fi
  fi

  log "Rollback completed."
  exit 1
}

trap 'rollback' ERR

main() {
  log "Starting deployment of version ${VERSION} to ${ENVIRONMENT}"

  check_prerequisites
  login_to_ghcr
  get_current_container
  determine_target_container
  pull_new_image
  backup_current_state
  start_new_container
  run_health_checks
  switch_traffic
  stop_old_container
  cleanup_old_images

  trap - ERR
  log "Deployment of version ${VERSION} to ${ENVIRONMENT} completed successfully."
}

main "$@"
