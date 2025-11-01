#!/bin/bash

set -euo pipefail

SCRIPT_NAME=$(basename "$0")

usage() {
  cat <<'USAGE'
Usage: ./scripts/secrets/setup_aws_secrets.sh --secret-name <name> --region <aws-region> [--update] [--create-policy]

Options:
  --secret-name      Name or ARN of the AWS Secrets Manager secret (required)
  --region           AWS region where the secret resides (required)
  --update           Update an existing secret instead of creating
  --create-policy    Create (or reuse) a minimal IAM policy for read access
  -h, --help         Show this help message and exit

Environment:
  AWS CLI credentials must be configured (profile, env vars, or instance role).
USAGE
}

SECRET_NAME=""
AWS_REGION=""
UPDATE_SECRET=false
CREATE_POLICY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --secret-name)
      SECRET_NAME="$2"
      shift 2
      ;;
    --region)
      AWS_REGION="$2"
      shift 2
      ;;
    --update)
      UPDATE_SECRET=true
      shift
      ;;
    --create-policy)
      CREATE_POLICY=true
      shift
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

if [[ -z "$SECRET_NAME" ]]; then
  echo "[$SCRIPT_NAME] Error: --secret-name is required" >&2
  exit 1
fi

if [[ -z "$AWS_REGION" ]]; then
  echo "[$SCRIPT_NAME] Error: --region is required" >&2
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "[$SCRIPT_NAME] Error: aws CLI is required" >&2
  exit 1
fi

if ! aws sts get-caller-identity --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "[$SCRIPT_NAME] Error: Unable to authenticate with AWS CLI" >&2
  exit 1
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

if [[ "$UPDATE_SECRET" == false ]]; then
  echo "[$SCRIPT_NAME] Creating secret $SECRET_NAME in $AWS_REGION"
  aws secretsmanager create-secret \
    --region "$AWS_REGION" \
    --name "$SECRET_NAME" \
    --secret-string "$PAYLOAD" \
    >/dev/null
else
  echo "[$SCRIPT_NAME] Updating secret $SECRET_NAME in $AWS_REGION"
  aws secretsmanager update-secret \
    --region "$AWS_REGION" \
    --secret-id "$SECRET_NAME" \
    --secret-string "$PAYLOAD" \
    >/dev/null
fi

aws secretsmanager get-secret-value \
  --region "$AWS_REGION" \
  --secret-id "$SECRET_NAME" \
  --query 'SecretString' \
  --output text \
  | python - <<'PY'
import json
import sys
try:
    json.loads(sys.stdin.read())
except json.JSONDecodeError as exc:
    print(f"Validation failed: {exc}", file=sys.stderr)
    sys.exit(1)
print("Secret JSON validated.")
PY

if [[ "$CREATE_POLICY" == true ]]; then
  ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
  POLICY_NAME=$(echo "${SECRET_NAME//[^A-Za-z0-9+=,.@_-]/-}-read")
  POLICY_DOC=$(mktemp)
  cat >"$POLICY_DOC" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:${SECRET_NAME}*"
    }
  ]
}
EOF
  EXISTING_ARN=$(aws iam list-policies --scope Local --query "Policies[?PolicyName=='${POLICY_NAME}'].Arn" --output text)
  if [[ -n "$EXISTING_ARN" && "$EXISTING_ARN" != "None" ]]; then
    echo "[$SCRIPT_NAME] Reusing existing policy: $EXISTING_ARN"
    POLICY_ARN="$EXISTING_ARN"
  else
    echo "[$SCRIPT_NAME] Creating IAM policy $POLICY_NAME"
    POLICY_ARN=$(aws iam create-policy \
      --policy-name "$POLICY_NAME" \
      --policy-document "file://$POLICY_DOC" \
      --query 'Policy.Arn' \
      --output text)
  fi
  rm -f "$POLICY_DOC"
  echo "[$SCRIPT_NAME] Attach policy to your compute role, e.g.:"
  echo "  aws iam attach-role-policy --role-name <role> --policy-arn $POLICY_ARN"
fi

echo "[$SCRIPT_NAME] Secret $SECRET_NAME provisioned successfully in $AWS_REGION."
