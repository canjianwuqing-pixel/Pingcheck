from fastapi import APIRouter, Depends, Query, Request

from app.dependencies import get_settings, require_admin
from app.modules.history.repository import list_recent_history
from app.modules.history.schemas import RecentHistoryResponse


router = APIRouter(
    prefix="/history",
    tags=["检测历史"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=list[RecentHistoryResponse])
def get_recent_history(
    request: Request,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[dict]:
    settings = get_settings(request)
    return list_recent_history(settings.database_path, limit)
