#!/bin/bash

set -euo pipefail

SCENARIO=${1:-mixed}
USERS=${2:-100}
SPAWN_RATE=${3:-10}
DURATION=${4:-5m}
HOST=${5:-http://localhost:8000}
LOCUST_FILE="tests/load/locustfile.py"
RESULTS_DIR="data/load_tests"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1"
}

check_prerequisites() {
  if ! command -v locust >/dev/null 2>&1; then
    echo "Locust is not installed. Install with 'pip install locust'." >&2
    exit 1
  fi

  if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required to run health checks." >&2
    exit 1
  fi

  mkdir -p "$RESULTS_DIR"

  if ! curl -sf "$HOST/health" >/dev/null; then
    echo "API health endpoint unavailable at $HOST/health" >&2
    exit 1
  fi
}

run_locust() {
  local scenario_name=$1
  local file=$2
  locust -f "$file" \
    --host "$HOST" \
    --users "$USERS" \
    --spawn-rate "$SPAWN_RATE" \
    --run-time "$DURATION" \
    --headless \
    --html "$RESULTS_DIR/${scenario_name}_report.html" \
    --csv "$RESULTS_DIR/${scenario_name}"
}

analyze_results() {
  local scenario_name=$1
  if command -v python >/dev/null 2>&1; then
    python scripts/load_testing/analyze_results.py \
      --stats-csv "$RESULTS_DIR/${scenario_name}_stats.csv" \
      --output both || true
  else
    log "Python not available; skipping automated analysis."
  fi
}

run_all_scenarios() {
  run_locust mixed "tests/load/locustfile.py"
  run_locust bulk "tests/load/scenarios/bulk_operations.py"
  run_locust export "tests/load/scenarios/export_heavy.py"
}

main() {
  check_prerequisites

  case "$SCENARIO" in
    mixed)
      log "Running mixed workload scenario..."
      run_locust mixed "$LOCUST_FILE"
      analyze_results mixed
      ;;
    bulk)
      log "Running bulk operations scenario..."
      run_locust bulk "tests/load/scenarios/bulk_operations.py"
      analyze_results bulk
      ;;
    export)
      log "Running export heavy scenario..."
      run_locust export "tests/load/scenarios/export_heavy.py"
      analyze_results export
      ;;
    all)
      log "Running all load testing scenarios sequentially..."
      run_all_scenarios
      analyze_results mixed
      analyze_results bulk
      analyze_results export
      ;;
    *)
      echo "Unknown scenario: $SCENARIO" >&2
      exit 1
      ;;
  esac

  log "Load testing complete. Reports stored in $RESULTS_DIR"
}

main "$@"
