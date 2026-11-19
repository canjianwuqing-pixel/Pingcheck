import asyncio
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
from app.modules.telegram.ss_config import ShadowsocksConfigManager


logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = TelegramClient(
            timeout=settings.telegram_timeout_seconds,
            max_attempts=settings.telegram_max_attempts,
            base_url=settings.telegram_api_base_url,
        )
        self.ss_config = ShadowsocksConfigManager(
            settings.shadowsocks_config_path,
            settings.shadowsocks_socks_port,
        )

    def sync_proxy_configuration(
        self, configuration: dict[str, Any] | None = None
    ) -> bool:
        current = configuration or get_telegram_settings(
            self.settings.database_path
        )
        return self.ss_config.sync(current)

    async def _ss_client_is_available(self) -> bool:
        writer: asyncio.StreamWriter | None = None
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self.settings.shadowsocks_socks_host,
                    self.settings.shadowsocks_socks_port,
                ),
                timeout=self.settings.shadowsocks_health_timeout_seconds,
            )
            return True
        except (OSError, TimeoutError):
            return False
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass

    async def _send(
        self, configuration: dict[str, Any], text: str
    ) -> TelegramSendResult:
        if configuration["proxy_type"] == "ss":
            if not await self._ss_client_is_available():
                return TelegramSendResult(False, "failed", "ss_unavailable")
        proxy_url = build_proxy_url(
            configuration,
            self.settings.shadowsocks_socks_host,
            self.settings.shadowsocks_socks_port,
        )
        return await self.client.send_message(
            configuration["bot_token"],
            configuration["chat_id"],
            text,
            proxy_url,
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
        result = await self._send(configuration, text)
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
        result = await self._send(
            configuration,
            f"✅ Pingcheck 测试消息\nTelegram 通知配置可用\n时间：{checked_at}",
        )
        logger.log(
            logging.INFO if result.success else logging.WARNING,
            "Telegram test notification result=%s",
            result.status,
        )
        return result

    def _format_target_message(self, event: str, target: dict[str, Any]) -> str:
        is_icmp = target["protocol"] == "ICMP"
        if event == "alert":
            title = "🚨 Pingcheck Ping 异常" if is_icmp else "🚨 Pingcheck 端口异常"
            state = f"异常（{target['protocol']} 连续失败达到 3 次）"
        else:
            title = "✅ Pingcheck Ping 恢复" if is_icmp else "✅ Pingcheck 端口恢复"
            state = "已恢复正常"
        checked_at = self._format_time(target["last_checked_at"])
        lines = [
            title,
            f"状态：{state}",
            f"入口：{target['name']}",
            f"IP：{target['ip']}",
        ]
        if target["port"] is not None:
            lines.append(f"端口：{target['port']}")
        lines.extend(
            [f"协议：{target['protocol']}", f"检测时间：{checked_at}"]
        )
        return "\n".join(lines)

    @staticmethod
    def _format_time(timestamp: int) -> str:
        return datetime.fromtimestamp(timestamp, timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
