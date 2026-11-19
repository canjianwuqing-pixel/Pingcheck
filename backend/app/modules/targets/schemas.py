from ipaddress import ip_address
from typing import Literal

from pydantic import BaseModel, Field, field_validator


Protocol = Literal["TCP", "UDP"]


class TargetWrite(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    ip: str = Field(min_length=1, max_length=45)
    port: int = Field(ge=1, le=65535)
    protocol: Protocol
    note: str = Field(default="", max_length=300)
    enabled: bool = True

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value: object) -> object:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("protocol", mode="before")
    @classmethod
    def normalize_protocol(cls, value: object) -> object:
        if isinstance(value, str):
            return value.upper()
        return value

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, value: str) -> str:
        try:
            return str(ip_address(value.strip()))
        except ValueError as error:
            raise ValueError("IP 地址格式不正确") from error


class TargetResponse(BaseModel):
    id: int
    name: str
    ip: str
    port: int
    protocol: Protocol
    note: str
    enabled: bool
    created_at: int
    updated_at: int


class TargetEnabledUpdate(BaseModel):
    enabled: bool
