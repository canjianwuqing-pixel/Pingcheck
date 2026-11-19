from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.dependencies import get_settings, require_admin
from app.modules.monitoring.repository import list_target_history
from app.modules.monitoring.service import (
    MonitorService,
    TargetDisabledError,
    TargetNotFoundError,
)
from app.modules.targets.repository import (
    create_target,
    delete_target,
    get_target,
    list_targets,
    update_target,
    update_target_enabled,
)
from app.modules.targets.schemas import (
    TargetEnabledUpdate,
    HistoryResponse,
    TargetResponse,
    TargetWrite,
)


router = APIRouter(
    prefix="/targets",
    tags=["入口管理"],
    dependencies=[Depends(require_admin)],
)


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="监控入口不存在",
    )


@router.get("", response_model=list[TargetResponse])
def get_targets(request: Request) -> list[dict]:
    settings = get_settings(request)
    return list_targets(settings.database_path)


@router.post("", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
def add_target(payload: TargetWrite, request: Request) -> dict:
    settings = get_settings(request)
    return create_target(settings.database_path, payload)


@router.get("/{target_id}", response_model=TargetResponse)
def get_target_detail(target_id: int, request: Request) -> dict:
    settings = get_settings(request)
    target = get_target(settings.database_path, target_id)
    if target is None:
        raise _not_found()
    return target


@router.put("/{target_id}", response_model=TargetResponse)
def edit_target(target_id: int, payload: TargetWrite, request: Request) -> dict:
    settings = get_settings(request)
    target = update_target(settings.database_path, target_id, payload)
    if target is None:
        raise _not_found()
    return target


@router.patch("/{target_id}/enabled", response_model=TargetResponse)
def set_target_enabled(
    target_id: int, payload: TargetEnabledUpdate, request: Request
) -> dict:
    settings = get_settings(request)
    target = update_target_enabled(
        settings.database_path, target_id, payload.enabled
    )
    if target is None:
        raise _not_found()
    return target


@router.post("/{target_id}/check", response_model=TargetResponse)
async def check_target_now(target_id: int, request: Request) -> dict:
    monitor: MonitorService = request.app.state.monitor
    try:
        return await monitor.check_target(target_id)
    except TargetNotFoundError:
        raise _not_found() from None
    except TargetDisabledError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="入口已暂停，请先启用",
        ) from None


@router.get("/{target_id}/history", response_model=list[HistoryResponse])
def get_target_history(
    target_id: int,
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict]:
    settings = get_settings(request)
    if get_target(settings.database_path, target_id) is None:
        raise _not_found()
    return list_target_history(settings.database_path, target_id, limit)


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_target(target_id: int, request: Request) -> Response:
    settings = get_settings(request)
    if not delete_target(settings.database_path, target_id):
        raise _not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
