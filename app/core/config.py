"""
Application Configuration
Verwendet Pydantic Settings für Type-Safe Configuration Management
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application Settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Database
    database_url: str = Field(
        default="postgresql://kr_user:kr_password_change_in_production@localhost:5432/kr_leads",
        description="PostgreSQL Database URL"
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
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="logs/scraper.log", description="Log file path")
    log_max_bytes: int = Field(default=10485760, description="Max log file size (10MB)")
    log_backup_count: int = Field(default=5, description="Number of log backups")
    
    # Environment
    debug: bool = Field(default=True, description="Debug mode")
    environment: str = Field(default="development", description="Environment")


# Global Settings Instance
settings = Settings()
