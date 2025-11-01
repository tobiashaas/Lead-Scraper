#!/bin/bash

set -euo pipefail

SCRIPT_NAME=$(basename "$0")

usage() {
  cat <<'USAGE'
Usage: ./scripts/secrets/setup_vault_secrets.sh --vault-addr <url> --vault-path <path> [--vault-token <token>]

Options:
  --vault-addr    Vault server address (e.g. https://vault.example.com) (required)
  --vault-path    KV v2 secret path, e.g. secret/data/kr-scraper (required)
  --vault-token   Vault token with manage permissions (optional if VAULT_TOKEN env var set)
  --policy-name   Name for the generated read/list policy (default: kr-scraper-app)
  --ttl           TTL for application token (default: 24h)
  -h, --help      Show this help message and exit

Environment:
  VAULT_TOKEN may be used instead of --vault-token.
USAGE
}

VAULT_ADDR=""
VAULT_PATH=""
VAULT_TOKEN="${VAULT_TOKEN:-}"
POLICY_NAME="kr-scraper-app"
TOKEN_TTL="24h"
VAULT_CLI_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vault-addr)
      VAULT_ADDR="$2"
      shift 2
      ;;
    --vault-path)
      VAULT_PATH="$2"
      shift 2
      ;;
    --vault-token)
      VAULT_TOKEN="$2"
      shift 2
      ;;
    --policy-name)
      POLICY_NAME="$2"
      shift 2
      ;;
    --ttl)
      TOKEN_TTL="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[$SCRIPT_NAME] Error: Unknown option $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$VAULT_ADDR" ]]; then
  echo "[$SCRIPT_NAME] Error: --vault-addr is required" >&2
  exit 1
fi

if [[ -z "$VAULT_PATH" ]]; then
  echo "[$SCRIPT_NAME] Error: --vault-path is required" >&2
  exit 1
fi

if [[ -z "$VAULT_TOKEN" ]]; then
  echo "[$SCRIPT_NAME] Error: --vault-token or VAULT_TOKEN must be provided" >&2
  exit 1
fi

export VAULT_ADDR
export VAULT_TOKEN

if ! command -v vault >/dev/null 2>&1; then
  echo "[$SCRIPT_NAME] Error: vault CLI is required" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "[$SCRIPT_NAME] Error: jq is required for JSON processing" >&2
  exit 1
fi

if ! vault status >/dev/null 2>&1; then
  echo "[$SCRIPT_NAME] Error: Unable to reach Vault at $VAULT_ADDR" >&2
  exit 1
fi

MOUNT="secret"
if ! vault secrets list --format=json | jq -e --arg mount "$MOUNT/" 'has($mount)' >/dev/null 2>&1; then
  echo "[$SCRIPT_NAME] Enabling KV v2 at $MOUNT/"
  vault secrets enable -path="$MOUNT" kv-v2 >/dev/null
fi

if [[ "$VAULT_PATH" == */data/* ]]; then
  VAULT_CLI_PATH="${VAULT_PATH//\/data/}"
else
  VAULT_CLI_PATH="$VAULT_PATH"
fi

PAYLOAD=$(python - <<'PY'
import json
import secrets
import string

def strong_password(length):
    alphabet = string.ascii_letters + string.digits + string.punctuation
    while True:
        candidate = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in candidate)
                and any(c.isupper() for c in candidate)
                and any(c.isdigit() for c in candidate)
                and any(c in string.punctuation for c in candidate)):
            return candidate

def tor_password(length):
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))

payload = {
    "SECRET_KEY": secrets.token_urlsafe(32),
    "POSTGRES_PASSWORD": strong_password(32),
    "REDIS_PASSWORD": strong_password(32),
    "TOR_CONTROL_PASSWORD": tor_password(24),
    "GOOGLE_PLACES_API_KEY": "",
    "TWOCAPTCHA_API_KEY": "",
    "SENTRY_DSN": "",
}

print(json.dumps(payload))
PY
)

if [[ -z "$PAYLOAD" ]]; then
  echo "[$SCRIPT_NAME] Error: Failed to generate payload" >&2
  exit 1
fi

TMP_PAYLOAD=$(mktemp)
POLICY_DOC=""
trap 'rm -f "$TMP_PAYLOAD" "$POLICY_DOC"' EXIT

printf '%s' "$PAYLOAD" >"$TMP_PAYLOAD"

vault kv put "$VAULT_CLI_PATH" @"$TMP_PAYLOAD" >/dev/null

if ! vault kv get "$VAULT_CLI_PATH" >/dev/null 2>&1; then
  echo "[$SCRIPT_NAME] Error: Failed to verify secret at $VAULT_PATH" >&2
  exit 1
fi

echo "[$SCRIPT_NAME] Writing read/list policy $POLICY_NAME"
POLICY_DOC=$(mktemp)
cat >"$POLICY_DOC" <<EOF
path "${VAULT_PATH}" {
  capabilities = ["read", "list"]
}
path "${VAULT_PATH}/*" {
  capabilities = ["read", "list"]
}
EOF
vault policy write "$POLICY_NAME" "$POLICY_DOC" >/dev/null

APP_TOKEN=$(vault token create -policy="$POLICY_NAME" -ttl="$TOKEN_TTL" -format=json | jq -r '.auth.client_token')

echo "[$SCRIPT_NAME] Application token (displayed once):"
echo "  $APP_TOKEN"
echo "Store this token securely; it will not be shown again."

echo "[$SCRIPT_NAME] Validate access with:"
echo "  VAULT_TOKEN=$APP_TOKEN vault kv get $VAULT_CLI_PATH"

echo "[$SCRIPT_NAME] Secret provisioning complete at $VAULT_PATH"
