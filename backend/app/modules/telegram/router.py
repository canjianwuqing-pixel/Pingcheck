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
        proxy_type=settings["proxy_type"],
        proxy_host=settings["proxy_host"],
        proxy_port=settings["proxy_port"],
        proxy_username=settings["proxy_username"],
        has_proxy_password=bool(settings["proxy_password"]),
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
    if payload.proxy_type != "direct":
        if not payload.proxy_host or payload.proxy_port is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="使用代理时请填写代理地址和端口",
            )
        if any(char in payload.proxy_host for char in "/@?#") or any(
            char.isspace() for char in payload.proxy_host
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="代理地址应填写主机名或 IP，不要包含协议或路径",
            )
    saved = save_telegram_settings(
        settings.database_path,
        bot_token=payload.bot_token,
        chat_id=payload.chat_id,
        enabled=payload.enabled,
        proxy_type=payload.proxy_type,
        proxy_host=payload.proxy_host,
        proxy_port=payload.proxy_port,
        proxy_username=payload.proxy_username,
        proxy_password=payload.proxy_password,
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
    failure_messages = {
        "timeout": "发送超时，请检查网络或代理连接",
        "proxy": "代理连接失败，请检查代理地址、端口和凭据",
        "network": "网络连接失败，请检查 Telegram API 地址或代理",
        "api": "Telegram API 返回失败，请检查 Bot Token、Chat ID 和 Bot 权限",
    }
    return TelegramTestResponse(
        success=False,
        message=failure_messages.get(
            result.reason if result is not None else None,
            "发送失败，请检查 Telegram 配置和网络连接",
        ),
    )
