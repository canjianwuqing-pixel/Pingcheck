from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.dependencies import get_settings, require_admin
from app.modules.telegram.repository import (
    get_telegram_settings,
    save_telegram_settings,
)
from app.modules.telegram.schemas import (
    TelegramSettingsResponse,
    TelegramSettingsUpdate,
    TelegramTestResponse,
)
from app.modules.telegram.service import TelegramService


router = APIRouter(
    prefix="/telegram",
    tags=["Telegram 通知"],
    dependencies=[Depends(require_admin)],
)


def _public_settings(settings: dict) -> TelegramSettingsResponse:
    return TelegramSettingsResponse(
        chat_id=settings["chat_id"],
        enabled=settings["enabled"],
        has_token=bool(settings["bot_token"]),
        updated_at=settings["updated_at"],
    )


@router.get("/settings", response_model=TelegramSettingsResponse)
def read_settings(request: Request) -> TelegramSettingsResponse:
    settings = get_settings(request)
    return _public_settings(get_telegram_settings(settings.database_path))


@router.put("/settings", response_model=TelegramSettingsResponse)
def update_settings(
    payload: TelegramSettingsUpdate, request: Request
) -> TelegramSettingsResponse:
    settings = get_settings(request)
    current = get_telegram_settings(settings.database_path)
    effective_token = payload.bot_token or current["bot_token"]
    if payload.enabled and (not effective_token or not payload.chat_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="启用通知前请填写 Bot Token 和 Chat ID",
        )
    saved = save_telegram_settings(
        settings.database_path,
        bot_token=payload.bot_token,
        chat_id=payload.chat_id,
        enabled=payload.enabled,
    )
    return _public_settings(saved)


@router.post("/test", response_model=TelegramTestResponse)
async def send_test_message(request: Request) -> TelegramTestResponse:
    settings = get_settings(request)
    configuration = get_telegram_settings(settings.database_path)
    if not configuration["bot_token"] or not configuration["chat_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先保存 Bot Token 和 Chat ID",
        )
    telegram: TelegramService = request.app.state.telegram
    result = await telegram.send_test_message()
    if result is not None and result.success:
        return TelegramTestResponse(success=True, message="测试消息已发送")
    return TelegramTestResponse(
        success=False,
        message="发送失败，请检查 Telegram 配置和网络连接",
    )
