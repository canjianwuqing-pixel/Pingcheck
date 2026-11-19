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

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )
