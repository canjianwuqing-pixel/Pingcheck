from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.dependencies import get_settings, require_admin
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


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_target(target_id: int, request: Request) -> Response:
    settings = get_settings(request)
    if not delete_target(settings.database_path, target_id):
        raise _not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
