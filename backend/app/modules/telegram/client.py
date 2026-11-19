import asyncio
import json
from dataclasses import dataclass
from typing import Literal
from urllib.request import Request, urlopen


SendStatus = Literal["sent", "failed"]


@dataclass(frozen=True)
class TelegramSendResult:
    success: bool
    status: SendStatus


class TelegramClient:
    def __init__(self, timeout: float, max_attempts: int) -> None:
        self.timeout = timeout
        self.max_attempts = max_attempts

    async def send_message(
        self, bot_token: str, chat_id: str, text: str
    ) -> TelegramSendResult:
        for attempt in range(self.max_attempts):
            sent = await asyncio.to_thread(
                self._post_message, bot_token, chat_id, text
            )
            if sent:
                return TelegramSendResult(True, "sent")
            if attempt + 1 < self.max_attempts:
                await asyncio.sleep(0.5)
        return TelegramSendResult(False, "failed")

    def _post_message(self, bot_token: str, chat_id: str, text: str) -> bool:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = json.dumps(
            {"chat_id": chat_id, "text": text}, ensure_ascii=False
        ).encode("utf-8")
        request = Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
                return response.status == 200 and body.get("ok") is True
        except (OSError, TimeoutError, ValueError):
            return False
