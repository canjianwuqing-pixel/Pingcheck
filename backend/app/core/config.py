from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or a local .env."""

    admin_password_hash: str
    session_secret: str = Field(min_length=16)
    session_max_age_seconds: int = Field(default=604800, ge=300)
    cookie_secure: bool = False
    database_path: Path = Path("data/pingcheck.db")
    monitor_interval_seconds: int = Field(default=60, ge=5)
    detection_timeout_seconds: float = Field(default=5.0, ge=0.1, le=30)
    max_concurrent_checks: int = Field(default=10, ge=1, le=100)
    history_retention_days: int = Field(default=30, ge=1)
    telegram_timeout_seconds: float = Field(default=5.0, ge=0.5, le=30)
    telegram_max_attempts: int = Field(default=2, ge=1, le=3)
    telegram_api_base_url: str = "https://api.telegram.org"
    shadowsocks_config_path: Path = Path("data/ss-client/config.json")
    shadowsocks_socks_host: str = "ss-client"
    shadowsocks_socks_port: int = Field(default=1080, ge=1, le=65535)
    shadowsocks_health_timeout_seconds: float = Field(default=1.0, ge=0.1, le=5)

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )
