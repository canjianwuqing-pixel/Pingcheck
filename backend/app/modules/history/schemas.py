from typing import Literal

from pydantic import BaseModel


class RecentHistoryResponse(BaseModel):
    id: int
    target_id: int
    target_name: str
    ip: str
    port: int | None
    protocol: Literal["ICMP", "TCP", "UDP"]
    status: Literal["success", "failure", "unknown"]
    latency_ms: float | None
    error_message: str | None
    checked_at: int
