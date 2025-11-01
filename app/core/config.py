"""
Application Configuration
Verwendet Pydantic Settings für Type-Safe Configuration Management
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, ClassVar
from urllib.parse import quote_plus

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.secrets_manager import (
    ProviderConfig,
    SecretsProvider,
    build_provider_config_from_env,
    get_secrets_provider,
    load_secrets_from_manager,
)


logger = logging.getLogger(__name__)

DEFAULT_SECRET_KEY = "your-secret-key-change-in-production-min-32-chars"
DEFAULT_POSTGRES_PASSWORD = "kr_password_change_in_production"
DEFAULT_DATABASE_URL = (
    f"postgresql://kr_user:{DEFAULT_POSTGRES_PASSWORD}@localhost:5432/kr_leads"
)
DEFAULT_REDIS_URL = "redis://localhost:6379"


class Settings(BaseSettings):
    """Application Settings"""

    _secrets_provider: ClassVar[SecretsProvider | None] = None
    _provider_config: ClassVar[ProviderConfig | None] = None
    _secrets_lock: ClassVar[threading.Lock] = threading.Lock()
    _secrets_cache: ClassVar[dict[str, Any] | None] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=(),
    )

    # Application
    app_name: str = Field(default="KR Lead Scraper API", description="Application Name")
    app_version: str = Field(default="1.0.0", description="Application Version")
    environment: str = Field(
        default="development", description="Environment (development, staging, production)"
    )
    debug: bool = Field(default=True, description="Debug Mode")

    # Security & JWT
    secret_key: str = Field(
        default="your-secret-key-change-in-production-min-32-chars",
        description="Secret key for JWT token generation",
    )
    algorithm: str = Field(default="HS256", description="JWT Algorithm")
    access_token_expire_minutes: int = Field(
        default=30, description="Access token expiration (minutes)"
    )
    refresh_token_expire_days: int = Field(default=7, description="Refresh token expiration (days)")

    # Database
    database_url: str = Field(
        default="postgresql://kr_user:kr_password_change_in_production@localhost:5432/kr_leads",
        description="PostgreSQL Database URL",
    )
    db_echo: bool = Field(default=False, description="Enable SQL query logging")

    # Database Connection Pooling
    db_pool_size: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Database connection pool size",
    )
    db_max_overflow: int = Field(
        default=40,
        ge=10,
        le=200,
        description="Max overflow connections beyond pool_size",
    )
    db_pool_timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Max seconds to wait for connection from pool",
    )
    db_pool_recycle: int = Field(
        default=3600,
        ge=300,
        le=7200,
        description="Recycle connections after N seconds",
    )
    db_connect_timeout: int = Field(
        default=10,
        ge=5,
        le=60,
        description="Database connection timeout (seconds)",
    )
    db_pool_pre_ping: bool = Field(
        default=True,
        description="Validate connections before use (pool_pre_ping)",
    )

    # Database Backup Configuration
    backup_enabled: bool = Field(default=True, description="Enable automated database backups")
    backup_daily_schedule: str = Field(
        default="0 3 * * *",
        description="Cron schedule for daily backups (3 AM)",
    )
    backup_weekly_schedule: str = Field(
        default="0 4 * * 0",
        description="Cron schedule for weekly backups (4 AM Sunday)",
    )
    backup_monthly_schedule: str = Field(
        default="0 5 1 * *",
        description="Cron schedule for monthly backups (5 AM 1st of month)",
    )
    backup_retention_daily: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Number of daily backups to retain",
    )
    backup_retention_weekly: int = Field(
        default=4,
        ge=1,
        le=12,
        description="Number of weekly backups to retain",
    )
    backup_retention_monthly: int = Field(
        default=12,
        ge=1,
        le=24,
        description="Number of monthly backups to retain",
    )
    backup_compression_enabled: bool = Field(
        default=True,
        description="Enable gzip compression for backups",
    )
    backup_encryption_enabled: bool = Field(
        default=False,
        description="Enable GPG encryption for backups",
    )
    backup_encryption_key: str = Field(
        default="",
        description="GPG key ID for backup encryption",
    )
    backup_cloud_sync_enabled: bool = Field(
        default=False,
        description="Enable cloud sync (S3, etc.)",
    )
    backup_cloud_provider: str = Field(
        default="s3",
        description="Cloud provider: s3, gcs, azure",
    )
    backup_cloud_bucket: str = Field(
        default="",
        description="Cloud storage bucket name",
    )
    backup_verification_enabled: bool = Field(
        default=True,
        description="Enable automated backup verification",
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", description="Redis URL")
    redis_db: int = Field(default=0, description="Redis Database Number")

    # RQ Worker Configuration
    rq_worker_count: int = Field(default=2, description="Number of RQ workers")
    rq_job_timeout: int = Field(default=3600, description="RQ job timeout in seconds")
    rq_result_ttl: int = Field(default=3600, description="RQ result TTL in seconds")
    rq_failure_ttl: int = Field(default=86400, description="RQ failure TTL in seconds")
    rq_retry_max: int = Field(default=3, description="Maximum retry attempts for RQ jobs")
    rq_retry_intervals: list[int] = Field(
        default_factory=lambda: [30, 60, 120],
        description="Retry backoff intervals in seconds for RQ jobs",
    )

    # Tor Configuration
    tor_enabled: bool = Field(default=True, description="Enable Tor Network")
    tor_proxy: str = Field(default="socks5://127.0.0.1:9050", description="Tor SOCKS Proxy")
    tor_control_port: int = Field(default=9051, description="Tor Control Port")
    tor_control_password: str = Field(default="", description="Tor Control Password")

    # Scraping Configuration
    scraping_delay_min: int = Field(default=3, description="Min delay between requests (seconds)")
    scraping_delay_max: int = Field(default=8, description="Max delay between requests (seconds)")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    request_timeout: int = Field(default=30, description="Request timeout (seconds)")

    # Rate Limiting
    rate_limit_requests: int = Field(default=10, description="Max requests per window")
    rate_limit_window: int = Field(default=60, description="Rate limit window (seconds)")

    # Playwright Settings
    playwright_browser: str = Field(default="firefox", description="Browser engine")
    playwright_headless: bool = Field(default=True, description="Run browser in headless mode")

    # Google Places API
    google_places_api_key: str = Field(default="", description="Google Places API Key")

    # CAPTCHA (optional)
    captcha_enabled: bool = Field(default=False, description="Enable CAPTCHA solving")
    twocaptcha_api_key: str = Field(default="", description="2Captcha API Key")

    # API
    api_host: str = Field(default="0.0.0.0", description="API Host")
    api_port: int = Field(default=8000, description="API Port")
    api_reload: bool = Field(default=True, description="Enable auto-reload")
    
    # API Configuration
    api_version: str = Field(default="1.0.0", description="API version (semantic versioning)")
    api_version_prefix: str = Field(default="/api/v1", description="API version URL prefix")
    api_deprecation_policy_url: str = Field(
        default="https://docs.your-domain.com/api/deprecation",
        description="URL to API deprecation policy"
    )
    api_base_url: str = Field(
        default="http://localhost:8000",
        description="Base URL for API (used in docs and webhooks)"
    )

    # CORS Configuration
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8080",
        description="Comma-separated list of allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(default=True, description="Allow credentials in CORS")
    cors_max_age: int = Field(default=600, description="CORS preflight cache duration (seconds)")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="logs/scraper.log", description="Log file path")
    log_max_bytes: int = Field(default=10485760, description="Max log file size (10MB)")
    log_backup_count: int = Field(default=5, description="Number of log backups")

    # Alerting & Notifications
    alerting_enabled: bool = Field(
        default=False,
        description="Enable global alerting and notification dispatch",
        validation_alias=AliasChoices("ALERTING_ENABLED", "alerting_enabled"),
    )
    alert_email_enabled: bool = Field(
        default=False,
        description="Enable email alerts",
        validation_alias=AliasChoices("ALERT_EMAIL_ENABLED", "alert_email_enabled"),
    )
    alert_email_to: str = Field(
        default="",
        description="Comma separated list of alert recipient email addresses",
        validation_alias=AliasChoices("ALERT_EMAIL_TO", "alert_email_to"),
    )
    alert_smtp_host: str = Field(
        default="",
        description="SMTP host for alert emails",
        validation_alias=AliasChoices("ALERT_SMTP_HOST", "alert_smtp_host"),
    )
    alert_smtp_port: int = Field(
        default=587,
        description="SMTP port for alert emails",
        validation_alias=AliasChoices("ALERT_SMTP_PORT", "alert_smtp_port"),
    )
    alert_smtp_user: str = Field(
        default="",
        description="SMTP username for alert emails",
        validation_alias=AliasChoices("ALERT_SMTP_USER", "alert_smtp_user"),
    )
    alert_smtp_password: str = Field(
        default="",
        description="SMTP password or app token for alert emails",
        validation_alias=AliasChoices("ALERT_SMTP_PASSWORD", "alert_smtp_password"),
    )
    alert_smtp_use_tls: bool = Field(
        default=True,
        description="Use STARTTLS when sending alert emails",
        validation_alias=AliasChoices("ALERT_SMTP_USE_TLS", "alert_smtp_use_tls"),
    )
    alert_from_email: str = Field(
        default="alerts@lead-scraper.local",
        description="From email address for alert emails",
        validation_alias=AliasChoices("ALERT_FROM_EMAIL", "alert_from_email"),
    )
    alert_slack_enabled: bool = Field(
        default=False,
        description="Enable Slack alerts",
        validation_alias=AliasChoices("ALERT_SLACK_ENABLED", "alert_slack_enabled"),
    )
    alert_slack_webhook_url: str = Field(
        default="",
        description="Slack webhook URL for alert delivery",
        validation_alias=AliasChoices("ALERT_SLACK_WEBHOOK_URL", "alert_slack_webhook_url"),
    )
    alert_slack_channel: str = Field(
        default="",
        description="Override Slack channel for alerts",
        validation_alias=AliasChoices("ALERT_SLACK_CHANNEL", "alert_slack_channel"),
    )
    alert_slack_username: str = Field(
        default="KR Lead Scraper",
        description="Display name for Slack alerts",
        validation_alias=AliasChoices("ALERT_SLACK_USERNAME", "alert_slack_username"),
    )
    alertmanager_url: str = Field(
        default="",
        description="Base URL for Alertmanager API",
        validation_alias=AliasChoices("ALERTMANAGER_URL", "alertmanager_url"),
    )

    # Sentry Error Tracking
    sentry_dsn: str = Field(default="", description="Sentry DSN for error tracking")
    sentry_environment: str = Field(default="development", description="Sentry environment")
    sentry_traces_sample_rate: float = Field(
        default=1.0, description="Sentry traces sample rate (0.0-1.0)"
    )
    sentry_profiles_sample_rate: float = Field(
        default=1.0, description="Sentry profiles sample rate (0.0-1.0)"
    )
    sentry_enabled: bool = Field(default=False, description="Enable Sentry error tracking")

    # Ollama Configuration
    ollama_host: str = Field(default="http://localhost:11434", description="Ollama API Host")
    ollama_model: str = Field(default="llama3.2", description="Default Ollama model")
    ollama_timeout: int = Field(default=120, description="Ollama request timeout (seconds)")

    ollama_model_selection_enabled: bool = Field(
        default=False,
        description="Enable automatic model selection based on use case",
    )
    ollama_model_priority: str = Field(
        default="balanced",
        description="Model selection priority: speed, accuracy, balanced, resource_efficient",
    )
    ollama_model_fast: str = Field(
        default="llama3.2:1b",
        description="Fast model for simple extractions",
    )
    ollama_model_accurate: str = Field(
        default="llama3.2",
        description="Accurate model for complex extractions",
    )
    ollama_model_balanced: str = Field(
        default="mistral",
        description="Balanced model for medium complexity extractions",
    )
    ollama_model_resource_efficient: str = Field(
        default="qwen2.5",
        description="Resource-efficient model for constrained environments",
    )
    ollama_benchmark_results_path: str = Field(
        default="data/benchmarks/ollama_results.json",
        description="Path to benchmark results JSON file",
    )
    ollama_prompt_optimization_enabled: bool = Field(
        default=False,
        description="Use optimized prompts from prompt library when available",
    )
    ollama_prompt_library_path: str = Field(
        default="data/prompts/optimized_prompts.json",
        description="Path to optimized prompt library",
    )

    # Crawl4AI Configuration
    crawl4ai_enabled: bool = Field(default=True, description="Enable Crawl4AI scraping")
    crawl4ai_word_count_threshold: int = Field(default=10, description="Minimum word count")
    crawl4ai_max_retries: int = Field(default=3, description="Max retries for Crawl4AI")

    # Smart Scraper Configuration
    smart_scraper_enabled: bool = Field(
        default=False, description="Enable Smart Scraper for website enrichment"
    )
    smart_scraper_mode: str = Field(
        default="enrichment",
        description="Smart scraper mode: enrichment, fallback, disabled",
    )
    smart_scraper_max_sites: int = Field(
        default=10,
        description="Max websites to scrape with smart scraper per job",
    )
    smart_scraper_preferred_method: str = Field(
        default="crawl4ai_ollama",
        description="Preferred scraping method for smart scraper",
    )
    smart_scraper_use_ai: bool = Field(
        default=True,
        description="Use AI extraction in smart scraper",
    )
    smart_scraper_timeout: int = Field(
        default=30,
        description="Timeout per website for smart scraper (seconds)",
    )

    # Deduplicator Configuration
    deduplicator_enabled: bool = Field(
        default=True,
        description="Enable automatic duplicate detection",
    )
    deduplicator_realtime_enabled: bool = Field(
        default=True,
        description="Enable real-time duplicate detection during scraping",
    )
    deduplicator_auto_merge_threshold: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Auto-merge duplicates above this similarity (0.95 = 95%)",
    )
    deduplicator_candidate_threshold: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Create duplicate candidates above this similarity (0.80 = 80%)",
    )
    deduplicator_name_threshold: int = Field(
        default=85,
        ge=0,
        le=100,
        description="Minimum name similarity for duplicates",
    )
    deduplicator_address_threshold: int = Field(
        default=80,
        ge=0,
        le=100,
        description="Minimum address similarity",
    )
    deduplicator_phone_threshold: int = Field(
        default=90,
        ge=0,
        le=100,
        description="Minimum phone similarity",
    )
    deduplicator_website_threshold: int = Field(
        default=95,
        ge=0,
        le=100,
        description="Minimum website similarity",
    )
    deduplicator_scan_schedule: str = Field(
        default="0 2 * * *",
        description="Cron schedule for duplicate scans (default: 2 AM daily)",
    )
    deduplicator_scan_batch_size: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Batch size for duplicate scans",
    )
    deduplicator_candidate_retention_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="Days to retain duplicate candidates before cleanup",
    )
    deduplicator_cleanup_delete_confirmed: bool = Field(
        default=False,
        description="Delete confirmed duplicate candidates during cleanup",
    )

    # Contact Verification Configuration
    email_verification_enabled: bool = Field(
        default=False,
        description="Enable email verification pipeline",
    )
    email_verification_method: str = Field(
        default="smtp",
        description="Verification method: smtp, api, or both",
    )
    email_verification_api_provider: str = Field(
        default="",
        description="Email verification API provider (zerobounce, hunter, emaillistverify)",
    )
    email_verification_api_key: str = Field(
        default="",
        description="API key for email verification provider",
    )
    email_verification_smtp_timeout: int = Field(
        default=10,
        ge=1,
        le=60,
        description="SMTP verification timeout in seconds",
    )
    email_verification_cache_ttl: int = Field(
        default=604800,
        description="Cache TTL for email verification results (seconds)",
    )
    email_verification_rate_limit: int = Field(
        default=10,
        ge=0,
        description="Max SMTP verifications per minute per domain",
    )

    phone_verification_enabled: bool = Field(
        default=False,
        description="Enable enhanced phone verification",
    )
    phone_verification_api_provider: str = Field(
        default="",
        description="Phone verification API provider (twilio, numverify)",
    )
    phone_verification_api_key: str = Field(
        default="",
        description="API key for phone verification provider",
    )

    verification_batch_schedule: str = Field(
        default="0 3 * * *",
        description="Cron schedule for nightly contact verification",
    )
    verification_batch_size: int = Field(
        default=100,
        ge=10,
        le=500,
        description="Batch size for contact verification jobs",
    )
    verification_max_concurrent: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Max concurrent verifications per worker",
    )
    verification_reverify_days: int = Field(
        default=30,
        ge=7,
        le=365,
        description="Re-verify contacts older than N days",
    )

    # Prometheus Metrics Configuration
    prometheus_enabled: bool = Field(
        default=True,
        description="Enable Prometheus metrics collection",
    )
    prometheus_multiproc_dir: str = Field(
        default="/tmp/prometheus_multiproc",
        description="Directory for Prometheus multiprocess metrics aggregation",
    )
    metrics_include_labels: bool = Field(
        default=True,
        description="Include detailed labels in Prometheus metrics",
    )
    metrics_endpoint_enabled: bool = Field(
        default=True,
        description="Enable /metrics endpoint exposure",
    )

    @classmethod
    def _initialize_secrets_provider(cls) -> None:
        """Initialise the secrets provider singleton from environment configuration."""

        with cls._secrets_lock:
            if cls._provider_config is None:
                cls._provider_config = build_provider_config_from_env()

            if cls._secrets_provider is None and cls._provider_config is not None:
                cls._secrets_provider = get_secrets_provider(
                    cls._provider_config.provider_type,
                    cls._provider_config,
                )

    @classmethod
    def _load_provider_secrets(cls) -> dict[str, Any]:
        """Load secrets from the configured provider once and cache the result."""

        cls._initialize_secrets_provider()

        if cls._secrets_cache is not None:
            return cls._secrets_cache

        provider = cls._secrets_provider
        config = cls._provider_config
        if provider is None or config is None:
            cls._secrets_cache = {}
            return cls._secrets_cache

        provider_type = (config.provider_type or "none").lower()
        secret_identifier = ""

        if provider_type == "aws":
            secret_identifier = config.aws_secret_name
        elif provider_type == "vault":
            secret_identifier = config.vault_path

        if not secret_identifier:
            logger.debug("Secrets provider configured without secret identifier; skipping fetch.")
            cls._secrets_cache = {}
            return cls._secrets_cache

        cls._secrets_cache = load_secrets_from_manager(secret_identifier, provider)
        return cls._secrets_cache

    @classmethod
    def _get_secret_value(cls, secret_key: str, env_var_name: str, default: Any) -> Any:
        """Resolve a configuration value from secrets manager, environment, or default."""

        secrets_payload = cls._load_provider_secrets()
        if secret_key and isinstance(secrets_payload, dict):
            secret_value = secrets_payload.get(secret_key)
            if secret_value not in (None, ""):
                return secret_value

        env_value = os.getenv(env_var_name)
        if env_value not in (None, ""):
            return env_value

        return default

    @model_validator(mode="after")
    def _apply_secrets(self) -> "Settings":
        """Populate secret-backed settings and validate provider configuration."""

        self.__class__._initialize_secrets_provider()
        config = self.__class__._provider_config
        provider_type = (config.provider_type if config else "none").lower()

        if provider_type == "aws":
            missing = [
                name
                for name, value in {
                    "AWS_REGION": config.aws_region,
                    "AWS_SECRETS_NAME": config.aws_secret_name,
                }.items()
                if not value
            ]
            if missing:
                raise ValueError(
                    "AWS secrets manager selected but required configuration missing: "
                    + ", ".join(missing)
                )
        elif provider_type == "vault":
            missing = [
                name
                for name, value in {
                    "VAULT_ADDR": config.vault_addr,
                    "VAULT_TOKEN": config.vault_token,
                    "VAULT_PATH": config.vault_path,
                }.items()
                if not value
            ]
            if missing:
                raise ValueError(
                    "Vault secrets manager selected but required configuration missing: "
                    + ", ".join(missing)
                )

        self.secret_key = self.__class__._get_secret_value(
            secret_key="secret_key",
            env_var_name="SECRET_KEY",
            default=self.secret_key or DEFAULT_SECRET_KEY,
        )

        database_url_secret = self.__class__._get_secret_value(
            secret_key="database_url",
            env_var_name="DATABASE_URL",
            default="",
        )

        if database_url_secret:
            self.database_url = database_url_secret
        else:
            db_user = self.__class__._get_secret_value(
                secret_key="postgres_user",
                env_var_name="POSTGRES_USER",
                default="kr_user",
            )
            db_password = self.__class__._get_secret_value(
                secret_key="postgres_password",
                env_var_name="POSTGRES_PASSWORD",
                default=DEFAULT_POSTGRES_PASSWORD,
            )
            db_host = self.__class__._get_secret_value(
                secret_key="postgres_host",
                env_var_name="POSTGRES_HOST",
                default="localhost",
            )
            db_port = self.__class__._get_secret_value(
                secret_key="postgres_port",
                env_var_name="POSTGRES_PORT",
                default="5432",
            )
            db_name = self.__class__._get_secret_value(
                secret_key="postgres_db",
                env_var_name="POSTGRES_DB",
                default="kr_leads",
            )

            self.database_url = (
                f"postgresql://{db_user}:{quote_plus(str(db_password))}@{db_host}:{db_port}/{db_name}"
            )

        self.redis_url = self.__class__._get_secret_value(
            secret_key="redis_url",
            env_var_name="REDIS_URL",
            default=self.redis_url or DEFAULT_REDIS_URL,
        )

        self.tor_control_password = self.__class__._get_secret_value(
            secret_key="tor_control_password",
            env_var_name="TOR_CONTROL_PASSWORD",
            default=self.tor_control_password,
        )

        self.google_places_api_key = self.__class__._get_secret_value(
            secret_key="google_places_api_key",
            env_var_name="GOOGLE_PLACES_API_KEY",
            default=self.google_places_api_key,
        )

        self.twocaptcha_api_key = self.__class__._get_secret_value(
            secret_key="twocaptcha_api_key",
            env_var_name="TWOCAPTCHA_API_KEY",
            default=self.twocaptcha_api_key,
        )

        self.email_verification_api_key = self.__class__._get_secret_value(
            secret_key="email_verification_api_key",
            env_var_name="EMAIL_VERIFICATION_API_KEY",
            default=self.email_verification_api_key,
        )

        self.phone_verification_api_key = self.__class__._get_secret_value(
            secret_key="phone_verification_api_key",
            env_var_name="PHONE_VERIFICATION_API_KEY",
            default=self.phone_verification_api_key,
        )

        self.alert_email_to = self.__class__._get_secret_value(
            secret_key="alert_email_to",
            env_var_name="ALERT_EMAIL_TO",
            default=self.alert_email_to,
        )

        self.alert_smtp_user = self.__class__._get_secret_value(
            secret_key="alert_smtp_user",
            env_var_name="ALERT_SMTP_USER",
            default=self.alert_smtp_user,
        )

        self.alert_smtp_password = self.__class__._get_secret_value(
            secret_key="alert_smtp_password",
            env_var_name="ALERT_SMTP_PASSWORD",
            default=self.alert_smtp_password,
        )

        self.alert_from_email = self.__class__._get_secret_value(
            secret_key="alert_from_email",
            env_var_name="ALERT_FROM_EMAIL",
            default=self.alert_from_email,
        )

        self.alert_slack_webhook_url = self.__class__._get_secret_value(
            secret_key="alert_slack_webhook_url",
            env_var_name="ALERT_SLACK_WEBHOOK_URL",
            default=self.alert_slack_webhook_url,
        )

        self.alert_slack_channel = self.__class__._get_secret_value(
            secret_key="alert_slack_channel",
            env_var_name="ALERT_SLACK_CHANNEL",
            default=self.alert_slack_channel,
        )

        self.alertmanager_url = self.__class__._get_secret_value(
            secret_key="alertmanager_url",
            env_var_name="ALERTMANAGER_URL",
            default=self.alertmanager_url,
        )

        self.backup_encryption_key = self.__class__._get_secret_value(
            secret_key="backup_encryption_key",
            env_var_name="BACKUP_ENCRYPTION_KEY",
            default=self.backup_encryption_key,
        )

        self.sentry_dsn = self.__class__._get_secret_value(
            secret_key="sentry_dsn",
            env_var_name="SENTRY_DSN",
            default=self.sentry_dsn,
        )

        return self

    @property
    def database_url_psycopg3(self) -> str:
        """
        Konvertiert DATABASE_URL für psycopg3 (SQLAlchemy 2.0+)
        postgresql:// -> postgresql+psycopg://
        """
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url

    @property
    def cors_origins_list(self) -> list[str]:
        """
        Konvertiert CORS origins string zu Liste
        """
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


# Global Settings Instance
settings = Settings()
