"""
Application Configuration
Verwendet Pydantic Settings für Type-Safe Configuration Management
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application Settings"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
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

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", description="Redis URL")
    redis_db: int = Field(default=0, description="Redis Database Number")

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

    # Environment
    debug: bool = Field(default=True, description="Debug mode")
    environment: str = Field(default="development", description="Environment")

    # Ollama Configuration
    ollama_host: str = Field(default="http://localhost:11434", description="Ollama API Host")
    ollama_model: str = Field(default="llama3.2", description="Default Ollama model")
    ollama_timeout: int = Field(default=120, description="Ollama request timeout (seconds)")

    # Crawl4AI Configuration
    crawl4ai_enabled: bool = Field(default=True, description="Enable Crawl4AI scraping")
    crawl4ai_word_count_threshold: int = Field(default=10, description="Minimum word count")
    crawl4ai_max_retries: int = Field(default=3, description="Max retries for Crawl4AI")

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
