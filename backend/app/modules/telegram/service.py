import logging
import time
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings
from app.modules.telegram.client import (
    TelegramClient,
    TelegramSendResult,
    build_proxy_url,
)
from app.modules.telegram.repository import get_telegram_settings


logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = TelegramClient(
            timeout=settings.telegram_timeout_seconds,
            max_attempts=settings.telegram_max_attempts,
            base_url=settings.telegram_api_base_url,
        )

    async def send_target_event(
        self, event: str, target: dict[str, Any]
    ) -> TelegramSendResult | None:
        configuration = get_telegram_settings(self.settings.database_path)
        if not configuration["enabled"]:
            return None
        if not configuration["bot_token"] or not configuration["chat_id"]:
            return None

        text = self._format_target_message(event, target)
        result = await self.client.send_message(
            configuration["bot_token"],
            configuration["chat_id"],
            text,
            build_proxy_url(configuration),
        )
        logger.log(
            logging.INFO if result.success else logging.WARNING,
            "Telegram target notification result=%s event=%s target_id=%s",
            result.status,
            event,
            target["id"],
        )
        return result

    async def send_test_message(self) -> TelegramSendResult | None:
        configuration = get_telegram_settings(self.settings.database_path)
        if not configuration["bot_token"] or not configuration["chat_id"]:
            return None
        checked_at = self._format_time(int(time.time()))
        result = await self.client.send_message(
            configuration["bot_token"],
            configuration["chat_id"],
            f"✅ Pingcheck 测试消息\nTelegram 通知配置可用\n时间：{checked_at}",
            build_proxy_url(configuration),
        )
        logger.log(
            logging.INFO if result.success else logging.WARNING,
            "Telegram test notification result=%s",
            result.status,
        )
        return result

    def _format_target_message(self, event: str, target: dict[str, Any]) -> str:
        if event == "alert":
            title = "🚨 Pingcheck 端口异常"
            state = "异常（TCP 连续失败达到 3 次）"
        else:
            title = "✅ Pingcheck 端口恢复"
            state = "已恢复正常"
        checked_at = self._format_time(target["last_checked_at"])
        return (
            f"{title}\n"
            f"状态：{state}\n"
            f"入口：{target['name']}\n"
            f"IP：{target['ip']}\n"
            f"端口：{target['port']}\n"
            f"协议：{target['protocol']}\n"
            f"检测时间：{checked_at}"
        )

    @staticmethod
    def _format_time(timestamp: int) -> str:
        return datetime.fromtimestamp(timestamp, timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
