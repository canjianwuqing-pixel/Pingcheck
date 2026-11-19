from typing import Literal

from pydantic import BaseModel, Field, field_validator


ProxyType = Literal["direct", "http", "https", "socks5"]


class TelegramSettingsResponse(BaseModel):
    chat_id: str
    enabled: bool
    has_token: bool
    proxy_type: ProxyType
    proxy_host: str
    proxy_port: int | None
    proxy_username: str
    has_proxy_password: bool
    updated_at: int | None


class TelegramSettingsUpdate(BaseModel):
    bot_token: str | None = Field(default=None, max_length=256)
    chat_id: str = Field(default="", max_length=100)
    enabled: bool = False
    proxy_type: ProxyType = "direct"
    proxy_host: str = Field(default="", max_length=255)
    proxy_port: int | None = Field(default=None, ge=1, le=65535)
    proxy_username: str = Field(default="", max_length=255)
    proxy_password: str | None = Field(default=None, max_length=256)

    @field_validator("bot_token", mode="before")
    @classmethod
    def normalize_token(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator("chat_id", "proxy_host", "proxy_username", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("proxy_password", mode="before")
    @classmethod
    def normalize_proxy_password(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            return value or None
        return value



class TelegramTestResponse(BaseModel):
    success: bool
    message: str
