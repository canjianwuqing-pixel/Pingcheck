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
from app.modules.telegram.client import (
    TelegramClient,
    TelegramSendResult,
    build_proxy_url,
)
from app.modules.telegram import client as telegram_client_module
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


def configure_telegram(
    client: TestClient,
    *,
    proxy_type: str = "direct",
    proxy_host: str = "",
    proxy_port: int | None = None,
    proxy_username: str = "",
    proxy_password: str | None = None,
) -> None:
    payload = {
        "bot_token": BOT_TOKEN,
        "chat_id": CHAT_ID,
        "enabled": True,
        "proxy_type": proxy_type,
        "proxy_host": proxy_host,
        "proxy_port": proxy_port,
        "proxy_username": proxy_username,
    }
    if proxy_password is not None:
        payload["proxy_password"] = proxy_password
    response = client.put(
        "/api/telegram/settings",
        json=payload,
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

    sent: list[tuple[str, str, str, str | None]] = []

    async def fake_send(
        token: str, chat_id: str, text: str, proxy_url: str | None
    ) -> TelegramSendResult:
        sent.append((token, chat_id, text, proxy_url))
        return TelegramSendResult(True, "sent")

    monkeypatch.setattr(client.app.state.telegram.client, "send_message", fake_send)
    caplog.set_level(logging.INFO)
    tested = client.post("/api/telegram/test")
    assert tested.status_code == 200
    assert tested.json() == {"success": True, "message": "测试消息已发送"}
    assert len(sent) == 1
    assert "Pingcheck 测试消息" in sent[0][2]
    assert sent[0][3] is None
    assert BOT_TOKEN not in caplog.text


def test_proxy_credentials_are_saved_but_never_returned(client: TestClient) -> None:
    login(client)
    configure_telegram(
        client,
        proxy_type="socks5",
        proxy_host="host.docker.internal",
        proxy_port=1080,
        proxy_username="proxy-user",
        proxy_password="proxy-secret-placeholder",
    )

    response = client.get("/api/telegram/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["proxy_type"] == "socks5"
    assert body["proxy_host"] == "host.docker.internal"
    assert body["proxy_port"] == 1080
    assert body["proxy_username"] == "proxy-user"
    assert body["has_proxy_password"] is True
    assert "proxy_password" not in body
    assert "proxy-secret-placeholder" not in response.text
    assert BOT_TOKEN not in response.text

    saved = get_telegram_settings(client.app.state.settings.database_path)
    assert saved["proxy_password"] == "proxy-secret-placeholder"

    preserved = client.put(
        "/api/telegram/settings",
        json={
            "chat_id": CHAT_ID,
            "enabled": True,
            "proxy_type": "socks5",
            "proxy_host": "host.docker.internal",
            "proxy_port": 1080,
            "proxy_username": "proxy-user",
        },
    )
    assert preserved.status_code == 200
    assert get_telegram_settings(
        client.app.state.settings.database_path
    )["proxy_password"] == "proxy-secret-placeholder"


def test_test_notification_reports_safe_proxy_failure(
    client: TestClient, monkeypatch, caplog
) -> None:
    login(client)
    configure_telegram(
        client,
        proxy_type="socks5",
        proxy_host="proxy.example.com",
        proxy_port=1080,
        proxy_username="private-user",
        proxy_password="private-password",
    )
    used_proxy_urls: list[str | None] = []

    async def failed_send(
        token: str, chat_id: str, text: str, proxy_url: str | None
    ) -> TelegramSendResult:
        used_proxy_urls.append(proxy_url)
        return TelegramSendResult(False, "failed", "proxy")

    monkeypatch.setattr(client.app.state.telegram.client, "send_message", failed_send)
    caplog.set_level(logging.WARNING)
    response = client.post("/api/telegram/test")
    assert response.status_code == 200
    assert response.json() == {
        "success": False,
        "message": "代理连接失败，请检查代理地址、端口和凭据",
    }
    assert used_proxy_urls == [
        "socks5h://private-user:private-password@proxy.example.com:1080"
    ]
    assert BOT_TOKEN not in response.text
    assert "private-password" not in response.text
    assert BOT_TOKEN not in caplog.text
    assert "private-password" not in caplog.text


def test_tcp_and_udp_probes_never_receive_telegram_proxy(
    client: TestClient, monkeypatch
) -> None:
    login(client)
    configure_telegram(
        client,
        proxy_type="http",
        proxy_host="proxy.example.com",
        proxy_port=8080,
    )
    calls: list[tuple[str, str, int, float]] = []

    async def direct_probe(
        protocol: str, ip: str, port: int, timeout: float
    ) -> ProbeResult:
        calls.append((protocol, ip, port, timeout))
        if protocol == "UDP":
            return ProbeResult("unknown", None, "未收到 UDP 响应")
        return ProbeResult("success", 1.0)

    monkeypatch.setattr(probes, "probe_target", direct_probe)
    tcp_target = add_target(client, protocol="TCP", name="TCP 直连")
    udp_target = add_target(client, protocol="UDP", name="UDP 直连")
    assert client.post(f"/api/targets/{tcp_target['id']}/check").status_code == 200
    assert client.post(f"/api/targets/{udp_target['id']}/check").status_code == 200
    assert [call[0] for call in calls] == ["TCP", "UDP"]
    assert all(call[1] == "192.0.2.40" and call[2] == 443 for call in calls)


def test_tcp_alert_recovery_and_deduplication(
    client: TestClient, monkeypatch
) -> None:
    login(client)
    configure_telegram(
        client,
        proxy_type="http",
        proxy_host="proxy.example.com",
        proxy_port=8080,
        proxy_username="notice-user",
        proxy_password="notice-password",
    )
    target = add_target(client, name="官网 HTTPS")
    messages: list[tuple[str, str | None]] = []

    async def fake_send(
        token: str, chat_id: str, text: str, proxy_url: str | None
    ) -> TelegramSendResult:
        messages.append((text, proxy_url))
        return TelegramSendResult(True, "sent")

    async def failed_probe(*args, **kwargs) -> ProbeResult:
        return ProbeResult("failure", 10.0, "连接超时")

    monkeypatch.setattr(client.app.state.telegram.client, "send_message", fake_send)
    monkeypatch.setattr(probes, "probe_target", failed_probe)

    for _ in range(4):
        response = client.post(f"/api/targets/{target['id']}/check")
        assert response.status_code == 200
    assert len(messages) == 1
    assert "端口异常" in messages[0][0]
    assert "官网 HTTPS" in messages[0][0]
    assert "192.0.2.40" in messages[0][0]
    assert "443" in messages[0][0]
    assert "TCP" in messages[0][0]
    assert "检测时间" in messages[0][0]
    assert messages[0][1] == (
        "http://notice-user:notice-password@proxy.example.com:8080"
    )

    async def successful_probe(*args, **kwargs) -> ProbeResult:
        return ProbeResult("success", 2.0)

    monkeypatch.setattr(probes, "probe_target", successful_probe)
    for _ in range(2):
        response = client.post(f"/api/targets/{target['id']}/check")
        assert response.status_code == 200
    assert len(messages) == 2
    assert "端口恢复" in messages[1][0]
    assert "已恢复正常" in messages[1][0]
    assert messages[1][1] == messages[0][1]


def test_udp_unknown_pause_and_delete_do_not_notify(
    client: TestClient, monkeypatch
) -> None:
    login(client)
    configure_telegram(client)
    messages: list[str] = []

    async def fake_send(
        token: str, chat_id: str, text: str, proxy_url: str | None
    ) -> TelegramSendResult:
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
        token: str, chat_id: str, text: str, proxy_url: str | None
    ) -> TelegramSendResult:
        nonlocal attempts
        attempts += 1
        return TelegramSendResult(False, "failed", "proxy")

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

    async def fail_then_succeed(
        token: str, chat_id: str, text: str, proxy_url: str | None
    ) -> TelegramSendResult:
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            return TelegramSendResult(True, "sent")
        return TelegramSendResult(False, "failed", "network")

    monkeypatch.setattr(telegram_client, "_post_message", fail_then_succeed)
    result = asyncio.run(telegram_client.send_message(BOT_TOKEN, CHAT_ID, "test"))
    assert result.success is True
    assert attempts == 2

    attempts = 0

    async def always_fail(
        token: str, chat_id: str, text: str, proxy_url: str | None
    ) -> TelegramSendResult:
        nonlocal attempts
        attempts += 1
        return TelegramSendResult(False, "failed", "proxy")

    monkeypatch.setattr(telegram_client, "_post_message", always_fail)
    failed = asyncio.run(telegram_client.send_message(BOT_TOKEN, CHAT_ID, "test"))
    assert failed.success is False
    assert failed.reason == "proxy"
    assert attempts == 2


def test_client_uses_configured_api_base_url_and_proxy(monkeypatch) -> None:
    requested_urls: list[str] = []
    client_options: list[dict] = []

    class FakeResponse:
        status_code = 200

        def json(self) -> dict:
            return {"ok": True}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            client_options.append(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

        async def post(self, url, json):
            requested_urls.append(url)
            return FakeResponse()

    monkeypatch.setattr(telegram_client_module.httpx, "AsyncClient", FakeAsyncClient)
    telegram_client = TelegramClient(
        timeout=1,
        max_attempts=1,
        base_url="https://telegram-api.example.com/",
    )
    proxy_urls = [
        None,
        "http://proxy.example.com:8080",
        "socks5h://proxy.example.com:1080",
    ]
    for proxy_url in proxy_urls:
        result = asyncio.run(
            telegram_client.send_message(
                BOT_TOKEN, CHAT_ID, "test", proxy_url
            )
        )
        assert result.success is True

    assert requested_urls == [
        f"https://telegram-api.example.com/bot{BOT_TOKEN}/sendMessage"
    ] * 3
    assert [options["proxy"] for options in client_options] == proxy_urls
    assert all(options["trust_env"] is False for options in client_options)


def test_build_proxy_url_supports_http_https_and_socks5h() -> None:
    configuration = {
        "proxy_type": "direct",
        "proxy_host": "",
        "proxy_port": None,
        "proxy_username": "",
        "proxy_password": "",
    }
    assert build_proxy_url(configuration) is None

    configuration.update(
        proxy_type="http",
        proxy_host="proxy.example.com",
        proxy_port=8080,
        proxy_username="user@name",
        proxy_password="secret:value",
    )
    assert build_proxy_url(configuration) == (
        "http://user%40name:secret%3Avalue@proxy.example.com:8080"
    )
    configuration["proxy_type"] = "https"
    assert build_proxy_url(configuration).startswith("https://")
    configuration["proxy_type"] = "socks5"
    assert build_proxy_url(configuration).startswith("socks5h://")


def test_client_reports_proxy_failure_without_sensitive_details(monkeypatch) -> None:
    class FailedAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

        async def post(self, url, json):
            raise telegram_client_module.httpx.ProxyError("private-proxy-secret")

    monkeypatch.setattr(
        telegram_client_module.httpx, "AsyncClient", FailedAsyncClient
    )
    telegram_client = TelegramClient(timeout=0.5, max_attempts=1)
    result = asyncio.run(
        telegram_client.send_message(
            BOT_TOKEN,
            CHAT_ID,
            "test",
            "socks5h://user:private-proxy-secret@proxy.example.com:1080",
        )
    )
    assert result == TelegramSendResult(False, "failed", "proxy")
    assert "private-proxy-secret" not in repr(result)


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
