from pydantic import BaseModel, Field, field_validator


class TelegramSettingsResponse(BaseModel):
    chat_id: str
    enabled: bool
    has_token: bool
    updated_at: int | None


class TelegramSettingsUpdate(BaseModel):
    bot_token: str | None = Field(default=None, max_length=256)
    chat_id: str = Field(default="", max_length=100)
    enabled: bool = False

    @field_validator("bot_token", mode="before")
    @classmethod
    def normalize_token(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator("chat_id", mode="before")
    @classmethod
    def normalize_chat_id(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class TelegramTestResponse(BaseModel):
    success: bool
    message: str
