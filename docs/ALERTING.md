# 🔔 Alerting & Notifications

Comprehensive alerting ensures incidents during scraping, API operations, and infrastructure outages are surfaced quickly. The Lead-Scraper stack ships with application-level notifications (email + Slack) and infrastructure alerting powered by Prometheus Alertmanager.

## 📘 Overview

- **Application alerts** are dispatched directly from the app using the `NotificationService` with Redis-backed deduplication.
- **Infrastructure alerts** originate from Prometheus rules and are routed by Alertmanager to email and Slack.
- **Templates** live in `app/templates/alerts` for emails/Slack and in `monitoring/alertmanager/templates` for Alertmanager.
- **Secrets** such as SMTP credentials and Slack webhooks are sourced from environment variables or the configured secrets manager.

## 🏗️ Architecture

```
Scraping Worker / API
        │
        │  async notification (email, Slack)
        ▼
NotificationService ── Redis (deduplication) ──▶ SMTP / Slack Webhook
        │
        │  Prometheus metrics + rules
        ▼
Prometheus ── Alertmanager ──▶ Email / Slack channels (routed by severity)
```

Key components:
- `app/utils/notifications.py` – core notification channels and dedup logic.
- `app/core/config.py` – alerting configuration and secrets loading.
- `monitoring/prometheus/alerts/*.rules.yml` – Prometheus alert rules.
- `monitoring/alertmanager/*.yml` – Alertmanager routing and receivers.

## ⚙️ Configuration

### Global toggles

| Variable | Description | Default |
| --- | --- | --- |
| `ALERTING_ENABLED` | Master switch for in-app notifications. | `False` |
| `ALERT_EMAIL_ENABLED` | Enable email alerts via SMTP. | `False` |
| `ALERT_SLACK_ENABLED` | Enable Slack webhook delivery. | `False` |
| `ALERTMANAGER_URL` | Base URL for Alertmanager API (optional). | `` |

### Email channel

| Variable | Description |
| --- | --- |
| `ALERT_EMAIL_TO` | Comma-separated list of alert recipients. |
| `ALERT_SMTP_HOST` / `ALERT_SMTP_PORT` | SMTP host and port (e.g., `smtp.sendgrid.net:587`). |
| `ALERT_SMTP_USER` / `ALERT_SMTP_PASSWORD` | SMTP credentials or app password. Stored in secrets manager in production. |
| `ALERT_SMTP_USE_TLS` | Enable STARTTLS (recommended). |
| `ALERT_FROM_EMAIL` | Sender address for alert emails. |

Provider notes:
- **Gmail** – generate an App Password and set `ALERT_SMTP_USER=your@gmail.com`, `ALERT_SMTP_PASSWORD=<app-password>`.
- **SendGrid** – set `ALERT_SMTP_USER=apikey` and `ALERT_SMTP_PASSWORD=<sendgrid-key>`.
- **Amazon SES** – use SMTP credentials generated in the AWS console.

### Slack channel

| Variable | Description |
| --- | --- |
| `ALERT_SLACK_WEBHOOK_URL` | Incoming webhook URL. |
| `ALERT_SLACK_CHANNEL` | Override channel (e.g., `#alerts`). Leave blank to use webhook default. |
| `ALERT_SLACK_USERNAME` | Display name for alert messages. |

Setup:
1. Create an **Incoming Webhook** in Slack (`https://myworkspace.slack.com/apps` → *Incoming Webhooks*).
2. Choose the default channel and copy the webhook URL into `ALERT_SLACK_WEBHOOK_URL`.
3. Optionally set `ALERT_SLACK_CHANNEL` to override the default destination per message.

### Secrets management

Sensitive values are automatically loaded through `_apply_secrets()` in `Settings`. Supported secret keys:

```
alert_email_to
alert_smtp_user
alert_smtp_password
alert_from_email
alert_slack_webhook_url
alert_slack_channel
alertmanager_url
```

Configure your secrets backend (AWS Secrets Manager / HashiCorp Vault) or environment to expose these keys.

## 🧩 Templates

| Template | Description |
| --- | --- |
| `app/templates/alerts/scraping_failure.*` | Email and text bodies for scraping job failures. |
| `app/templates/alerts/slack_scraping_failure.json` | Slack Block Kit payload for scraping failures. |
| `monitoring/alertmanager/templates/email.tmpl` | Alertmanager email template. |
| `monitoring/alertmanager/templates/slack.tmpl` | Alertmanager Slack message template. |

Slack templates now use top-level `blocks` for compatibility with the in-app Slack channel implementation.

## 🚦 Routing & Deduplication

- Alertmanager routes by `severity` into `critical-alerts`, `warning-alerts`, and `info-alerts` receivers.
- The application `NotificationService` creates deduplication keys based on alert type, job ID, issue type, or custom `dedup_key` in the context. Redis stores these keys for 5 minutes to prevent alert floods.
- Override routing by adjusting `monitoring/alertmanager/alertmanager.yml` / `.prod.yml` or by supplying alternative environment variables during deployment.

## ✅ Testing & Validation

| Command | Purpose |
| --- | --- |
| `make alertmanager-up` | Start only Alertmanager (with configuration templates). |
| `make alertmanager` | Tail Alertmanager logs for debugging. |
| `make validate-alert-rules` | Run `promtool check rules` against Prometheus rules. |
| `make test-alerts` | Execute alerting-focused unit/integration tests (requires test suite). |
| `make monitoring-up` | Start Prometheus, Grafana, **and Alertmanager** together. |

Manual checks:
1. Trigger a scraping failure (e.g., enqueue a job with invalid configuration) and confirm email/Slack delivery.
2. Use `amtool check-config monitoring/alertmanager/alertmanager.yml` for static validation (requires `amtool`).
3. Visit Grafana dashboards to verify alert annotations when Prometheus rules fire.

## 🧰 Troubleshooting

| Symptom | Suggested fix |
| --- | --- |
| Email alerts missing | Verify SMTP credentials and that `ALERT_EMAIL_ENABLED=True` and `ALERT_EMAIL_TO` is populated. Check SMTP logs for authentication failures. |
| Slack alerts missing | Confirm webhook URL and ensure the workspace allows incoming webhooks. Test by `curl -X POST -H 'Content-type: application/json' --data '{"text":"test"}' $ALERT_SLACK_WEBHOOK_URL`. |
| Duplicate alerts | Ensure Redis is reachable; check `NotificationService` logs for dedup warnings. Increase TTL if alerts recur too frequently. |
| Alertmanager not starting | Run `make alertmanager` and inspect logs for YAML parsing errors. Validate with `make validate-alert-rules`. |
| Prometheus rules invalid | See `make validate-alert-rules` output and adjust rule syntax (especially nested quotes in annotations). |

## 📚 Related Documentation

- [Monitoring Guide](./MONITORING.md)
- [`app/utils/notifications.py`](../app/utils/notifications.py)
- [`monitoring/alertmanager/alertmanager.yml`](../monitoring/alertmanager/alertmanager.yml)
- [`monitoring/prometheus/alerts/system.rules.yml`](../monitoring/prometheus/alerts/system.rules.yml)

With alerting configured, you can route incidents to the right on-call channel and keep your scraping pipeline healthy.
