from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app import __version__
from app.database import database_is_ready
from app.dependencies import get_settings


router = APIRouter(tags=["系统"])


class HealthState(BaseModel):
    status: str
    version: str
    database: str


@router.get("/health", response_model=HealthState)
def health(request: Request) -> HealthState:
    settings = get_settings(request)
    ready = database_is_ready(settings.database_path)
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="数据库不可用",
        )
    return HealthState(
        status="ok",
        version=__version__,
        database="ok",
    )
