import asyncio
from dataclasses import dataclass
from typing import Literal

import httpx


SendStatus = Literal["sent", "failed"]
FailureReason = Literal["timeout", "proxy", "network", "api", "ss_unavailable"]


@dataclass(frozen=True)
class TelegramSendResult:
    success: bool
    status: SendStatus
    reason: FailureReason | None = None


class TelegramClient:
    def __init__(
        self,
        timeout: float,
        max_attempts: int,
        base_url: str = "https://api.telegram.org",
    ) -> None:
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.base_url = base_url.strip().rstrip("/")

    async def send_message(
        self,
        bot_token: str,
        chat_id: str,
        text: str,
        proxy_url: str | None = None,
    ) -> TelegramSendResult:
        last_result = TelegramSendResult(False, "failed", "network")
        for attempt in range(self.max_attempts):
            last_result = await self._post_message(
                bot_token, chat_id, text, proxy_url
            )
            if last_result.success:
                return last_result
            if attempt + 1 < self.max_attempts:
                await asyncio.sleep(0.5)
        return last_result

    async def _post_message(
        self,
        bot_token: str,
        chat_id: str,
        text: str,
        proxy_url: str | None,
    ) -> TelegramSendResult:
        url = f"{self.base_url}/bot{bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(
                proxy=proxy_url,
                timeout=self.timeout,
                trust_env=False,
            ) as client:
                response = await client.post(
                    url,
                    json={"chat_id": chat_id, "text": text},
                )
            body = response.json()
            if (
                response.status_code == 200
                and isinstance(body, dict)
                and body.get("ok") is True
            ):
                return TelegramSendResult(True, "sent")
            return TelegramSendResult(False, "failed", "api")
        except httpx.TimeoutException:
            reason: FailureReason = "proxy" if proxy_url else "timeout"
            return TelegramSendResult(False, "failed", reason)
        except (httpx.ProxyError, httpx.ConnectError):
            reason: FailureReason = "proxy" if proxy_url else "network"
            return TelegramSendResult(False, "failed", reason)
        except (httpx.HTTPError, ValueError):
            return TelegramSendResult(False, "failed", "network")


def build_proxy_url(
    configuration: dict,
    ss_proxy_host: str = "ss-client",
    ss_proxy_port: int = 1080,
) -> str | None:
    proxy_type = configuration["proxy_type"]
    if proxy_type == "direct":
        return None
    if proxy_type == "ss":
        return str(
            httpx.URL(
                scheme="socks5h",
                host=ss_proxy_host,
                port=ss_proxy_port,
            )
        )
    scheme = "socks5h" if proxy_type == "socks5" else proxy_type
    url_options: dict[str, object] = {
        "scheme": scheme,
        "host": configuration["proxy_host"],
        "port": configuration["proxy_port"],
    }
    if configuration["proxy_username"]:
        url_options["username"] = configuration["proxy_username"]
    if configuration["proxy_password"]:
        url_options["password"] = configuration["proxy_password"]
    return str(httpx.URL(**url_options))
