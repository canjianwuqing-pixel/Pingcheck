import asyncio
import logging
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.database import connect, initialize_database
from app.modules.monitoring import probes
from app.modules.monitoring.probes import ProbeResult
from app.modules.monitoring.service import MonitorService
from app.modules.targets.repository import create_target
from app.modules.targets.schemas import TargetWrite
from app.modules.telegram.client import TelegramClient, TelegramSendResult
from app.modules.telegram.repository import (
    get_telegram_settings,
    save_telegram_settings,
)


BOT_TOKEN = "test-bot-token-placeholder"
CHAT_ID = "-1001234567890"


def login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"password": "correct-password"}
    )
    assert response.status_code == 200


def configure_telegram(client: TestClient) -> None:
    response = client.put(
        "/api/telegram/settings",
        json={"bot_token": BOT_TOKEN, "chat_id": CHAT_ID, "enabled": True},
    )
    assert response.status_code == 200
    assert response.json()["has_token"] is True
    assert "bot_token" not in response.json()


def add_target(client: TestClient, protocol: str = "TCP", name: str = "主站") -> dict:
    response = client.post(
        "/api/targets",
        json={
            "name": name,
            "ip": "192.0.2.40",
            "port": 443,
            "protocol": protocol,
            "note": "",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_settings_hide_token_and_send_test_message(
    client: TestClient, monkeypatch, caplog
) -> None:
    assert client.get("/api/telegram/settings").status_code == 401
    login(client)
    invalid = client.put(
        "/api/telegram/settings",
        json={"chat_id": CHAT_ID, "enabled": True},
    )
    assert invalid.status_code == 400

    configure_telegram(client)
    saved = client.get("/api/telegram/settings")
    assert saved.status_code == 200
    assert saved.json()["chat_id"] == CHAT_ID
    assert saved.json()["enabled"] is True
    assert saved.json()["has_token"] is True
    assert BOT_TOKEN not in saved.text

    sent: list[tuple[str, str, str]] = []

    async def fake_send(token: str, chat_id: str, text: str) -> TelegramSendResult:
        sent.append((token, chat_id, text))
        return TelegramSendResult(True, "sent")

    monkeypatch.setattr(client.app.state.telegram.client, "send_message", fake_send)
    caplog.set_level(logging.INFO)
    tested = client.post("/api/telegram/test")
    assert tested.status_code == 200
    assert tested.json() == {"success": True, "message": "测试消息已发送"}
    assert len(sent) == 1
    assert "Pingcheck 测试消息" in sent[0][2]
    assert BOT_TOKEN not in caplog.text


def test_tcp_alert_recovery_and_deduplication(
    client: TestClient, monkeypatch
) -> None:
    login(client)
    configure_telegram(client)
    target = add_target(client, name="官网 HTTPS")
    messages: list[str] = []

    async def fake_send(token: str, chat_id: str, text: str) -> TelegramSendResult:
        messages.append(text)
        return TelegramSendResult(True, "sent")

    async def failed_probe(*args, **kwargs) -> ProbeResult:
        return ProbeResult("failure", 10.0, "连接超时")

    monkeypatch.setattr(client.app.state.telegram.client, "send_message", fake_send)
    monkeypatch.setattr(probes, "probe_target", failed_probe)

    for _ in range(4):
        response = client.post(f"/api/targets/{target['id']}/check")
        assert response.status_code == 200
    assert len(messages) == 1
    assert "端口异常" in messages[0]
    assert "官网 HTTPS" in messages[0]
    assert "192.0.2.40" in messages[0]
    assert "443" in messages[0]
    assert "TCP" in messages[0]
    assert "检测时间" in messages[0]

    async def successful_probe(*args, **kwargs) -> ProbeResult:
        return ProbeResult("success", 2.0)

    monkeypatch.setattr(probes, "probe_target", successful_probe)
    for _ in range(2):
        response = client.post(f"/api/targets/{target['id']}/check")
        assert response.status_code == 200
    assert len(messages) == 2
    assert "端口恢复" in messages[1]
    assert "已恢复正常" in messages[1]


def test_udp_unknown_pause_and_delete_do_not_notify(
    client: TestClient, monkeypatch
) -> None:
    login(client)
    configure_telegram(client)
    messages: list[str] = []

    async def fake_send(token: str, chat_id: str, text: str) -> TelegramSendResult:
        messages.append(text)
        return TelegramSendResult(True, "sent")

    async def unknown_probe(*args, **kwargs) -> ProbeResult:
        return ProbeResult("unknown", None, "未收到 UDP 响应")

    monkeypatch.setattr(client.app.state.telegram.client, "send_message", fake_send)
    monkeypatch.setattr(probes, "probe_target", unknown_probe)
    udp_target = add_target(client, protocol="UDP", name="UDP 服务")
    for _ in range(4):
        client.post(f"/api/targets/{udp_target['id']}/check")
    assert messages == []

    async def failed_probe(*args, **kwargs) -> ProbeResult:
        return ProbeResult("failure", 8.0, "连接失败")

    monkeypatch.setattr(probes, "probe_target", failed_probe)
    tcp_target = add_target(client, name="暂停测试")
    for _ in range(2):
        client.post(f"/api/targets/{tcp_target['id']}/check")
    client.patch(
        f"/api/targets/{tcp_target['id']}/enabled", json={"enabled": False}
    )
    assert client.post(f"/api/targets/{tcp_target['id']}/check").status_code == 409
    assert client.delete(f"/api/targets/{tcp_target['id']}").status_code == 204
    assert messages == []


def test_notification_failure_does_not_break_monitoring_or_repeat(
    client: TestClient, monkeypatch, caplog
) -> None:
    login(client)
    configure_telegram(client)
    target = add_target(client, name="失败通知测试")
    attempts = 0

    async def failed_send(
        token: str, chat_id: str, text: str
    ) -> TelegramSendResult:
        nonlocal attempts
        attempts += 1
        return TelegramSendResult(False, "failed")

    async def failed_probe(*args, **kwargs) -> ProbeResult:
        return ProbeResult("failure", 9.0, "连接被拒绝")

    monkeypatch.setattr(client.app.state.telegram.client, "send_message", failed_send)
    monkeypatch.setattr(probes, "probe_target", failed_probe)
    caplog.set_level(logging.WARNING)
    responses = [
        client.post(f"/api/targets/{target['id']}/check") for _ in range(4)
    ]
    assert all(response.status_code == 200 for response in responses)
    assert responses[-1].json()["status"] == "abnormal"
    assert attempts == 1
    assert BOT_TOKEN not in caplog.text


def test_client_uses_limited_retry(monkeypatch) -> None:
    telegram_client = TelegramClient(timeout=0.5, max_attempts=2)
    attempts = 0

    def fail_then_succeed(token: str, chat_id: str, text: str) -> bool:
        nonlocal attempts
        attempts += 1
        return attempts == 2

    monkeypatch.setattr(telegram_client, "_post_message", fail_then_succeed)
    result = asyncio.run(telegram_client.send_message(BOT_TOKEN, CHAT_ID, "test"))
    assert result.success is True
    assert attempts == 2

    attempts = 0

    def always_fail(token: str, chat_id: str, text: str) -> bool:
        nonlocal attempts
        attempts += 1
        return False

    monkeypatch.setattr(telegram_client, "_post_message", always_fail)
    failed = asyncio.run(telegram_client.send_message(BOT_TOKEN, CHAT_ID, "test"))
    assert failed.success is False
    assert attempts == 2


def test_alert_state_survives_service_restart(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(
        admin_password_hash=hash_password("test", salt="telegram-salt"),
        session_secret="telegram-session-secret-long-enough",
        database_path=tmp_path / "telegram.db",
    )
    initialize_database(settings.database_path)
    save_telegram_settings(
        settings.database_path,
        bot_token=BOT_TOKEN,
        chat_id=CHAT_ID,
        enabled=True,
    )
    target = create_target(
        settings.database_path,
        TargetWrite(
            name="持久化告警",
            ip="198.51.100.30",
            port=443,
            protocol="TCP",
        ),
    )
    outcome = ProbeResult("failure", 5.0, "连接超时")

    async def controlled_probe(*args, **kwargs) -> ProbeResult:
        return outcome

    class FakeNotifier:
        def __init__(self) -> None:
            self.events: list[str] = []

        async def send_target_event(self, event: str, checked_target: dict):
            self.events.append(event)
            return TelegramSendResult(True, "sent")

    monkeypatch.setattr(probes, "probe_target", controlled_probe)

    async def scenario() -> tuple[list[str], list[str]]:
        nonlocal outcome
        first_notifier = FakeNotifier()
        first_service = MonitorService(settings, first_notifier)
        for _ in range(3):
            await first_service.check_target(target["id"])

        second_notifier = FakeNotifier()
        restarted_service = MonitorService(settings, second_notifier)
        await restarted_service.check_target(target["id"])
        outcome = ProbeResult("success", 1.0)
        await restarted_service.check_target(target["id"])
        return first_notifier.events, second_notifier.events

    first_events, restarted_events = asyncio.run(scenario())
    assert first_events == ["alert"]
    assert restarted_events == ["recovery"]
    with connect(settings.database_path) as connection:
        alert_active = connection.execute(
            "SELECT alert_active FROM check_targets WHERE id = ?", (target["id"],)
        ).fetchone()[0]
    assert alert_active == 0
    assert get_telegram_settings(settings.database_path)["bot_token"] == BOT_TOKEN
