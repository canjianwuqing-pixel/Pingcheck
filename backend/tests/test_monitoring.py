import asyncio
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.database import connect, initialize_database
from app.modules.monitoring import probes
from app.modules.monitoring.probes import ProbeResult
from app.modules.monitoring.repository import cleanup_old_history
from app.modules.monitoring.service import MonitorService
from app.modules.targets.repository import create_target
from app.modules.targets.schemas import TargetWrite


def login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"password": "correct-password"}
    )
    assert response.status_code == 200


def add_target(client: TestClient, protocol: str = "TCP") -> dict:
    response = client.post(
        "/api/targets",
        json={
            "name": f"{protocol} 测试入口",
            "ip": "192.0.2.30",
            "port": 443,
            "protocol": protocol,
            "note": "",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_tcp_three_failures_and_recovery(client: TestClient, monkeypatch) -> None:
    login(client)
    target = add_target(client)

    async def fail_probe(*args, **kwargs) -> ProbeResult:
        return ProbeResult("failure", 12.5, "连接超时")

    monkeypatch.setattr(probes, "probe_target", fail_probe)
    states = []
    for _ in range(3):
        response = client.post(f"/api/targets/{target['id']}/check")
        assert response.status_code == 200
        states.append(response.json())

    assert [item["status"] for item in states] == [
        "warning",
        "warning",
        "abnormal",
    ]
    assert states[-1]["consecutive_failures"] == 3

    async def successful_probe(*args, **kwargs) -> ProbeResult:
        return ProbeResult("success", 3.25)

    monkeypatch.setattr(probes, "probe_target", successful_probe)
    recovered = client.post(f"/api/targets/{target['id']}/check")
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "normal"
    assert recovered.json()["consecutive_failures"] == 0
    assert recovered.json()["last_latency_ms"] == 3.25

    history = client.get(f"/api/targets/{target['id']}/history")
    assert history.status_code == 200
    assert [item["status"] for item in history.json()] == [
        "success",
        "failure",
        "failure",
        "failure",
    ]


def test_udp_unknown_does_not_increment_failures(client: TestClient, monkeypatch) -> None:
    login(client)
    target = add_target(client, "UDP")

    async def unknown_probe(*args, **kwargs) -> ProbeResult:
        return ProbeResult("unknown", None, "未收到 UDP 响应")

    monkeypatch.setattr(probes, "probe_target", unknown_probe)
    for _ in range(3):
        response = client.post(f"/api/targets/{target['id']}/check")
        assert response.status_code == 200
        assert response.json()["status"] == "unknown"
        assert response.json()["consecutive_failures"] == 0

    async def unreachable_probe(*args, **kwargs) -> ProbeResult:
        return ProbeResult("failure", 1.5, "UDP 端口明确不可达")

    monkeypatch.setattr(probes, "probe_target", unreachable_probe)
    unreachable = client.post(f"/api/targets/{target['id']}/check")
    assert unreachable.json()["status"] == "abnormal"
    assert unreachable.json()["consecutive_failures"] == 1

    client.patch(f"/api/targets/{target['id']}/enabled", json={"enabled": False})
    paused = client.post(f"/api/targets/{target['id']}/check")
    assert paused.status_code == 409


def test_history_cleanup_removes_only_expired_rows(client: TestClient) -> None:
    login(client)
    target = add_target(client)
    database_path = client.app.state.settings.database_path
    now = int(time.time())
    with connect(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO check_history(target_id, status, latency_ms, error_message, checked_at)
            VALUES (?, 'success', 1.0, NULL, ?)
            """,
            [
                (target["id"], now - 31 * 86400),
                (target["id"], now - 10),
            ],
        )

    assert cleanup_old_history(database_path, 30) == 1
    history = client.get(f"/api/targets/{target['id']}/history").json()
    assert len(history) == 1


def test_scheduler_avoids_duplicates_and_limits_concurrency(
    tmp_path: Path, monkeypatch
) -> None:
    settings = Settings(
        admin_password_hash=hash_password("test", salt="monitor-salt"),
        session_secret="monitor-session-secret-long-enough",
        database_path=tmp_path / "monitor.db",
        max_concurrent_checks=2,
    ).model_copy(update={"monitor_interval_seconds": 0.05})
    initialize_database(settings.database_path)
    for index in range(5):
        create_target(
            settings.database_path,
            TargetWrite(
                name=f"入口 {index}",
                ip=f"192.0.2.{index + 1}",
                port=80,
                protocol="TCP",
            ),
        )
    create_target(
        settings.database_path,
        TargetWrite(
            name="暂停入口",
            ip="192.0.2.100",
            port=80,
            protocol="TCP",
            enabled=False,
        ),
    )

    active = 0
    peak = 0
    checked_ips: list[str] = []

    async def tracked_probe(protocol, ip, port, timeout) -> ProbeResult:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        checked_ips.append(ip)
        await asyncio.sleep(0.01)
        active -= 1
        return ProbeResult("success", 1.0)

    monkeypatch.setattr(probes, "probe_target", tracked_probe)

    async def scenario() -> None:
        service = MonitorService(settings)
        assert settings.monitor_interval_seconds == 0.05
        await service.start()
        first_task = service._task
        await service.start()
        assert service._task is first_task
        await asyncio.sleep(0.25)
        await service.stop()

    asyncio.run(scenario())
    assert peak == 2
    assert len(checked_ips) >= 10
    assert "192.0.2.100" not in checked_ips
