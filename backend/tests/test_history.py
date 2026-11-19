from fastapi.testclient import TestClient

from app.modules.monitoring.probes import ProbeResult
from app.modules.monitoring.repository import record_probe_result


def test_recent_history_requires_login_and_returns_target_details(
    client: TestClient,
) -> None:
    assert client.get("/api/history").status_code == 401
    client.post("/api/auth/login", json={"password": "correct-password"})
    created = client.post(
        "/api/targets",
        json={
            "name": "历史测试入口",
            "ip": "192.0.2.55",
            "port": 8443,
            "protocol": "TCP",
            "note": "",
        },
    ).json()
    database_path = client.app.state.settings.database_path
    record_probe_result(
        database_path, created["id"], ProbeResult("failure", 5.5, "连接失败")
    )
    record_probe_result(
        database_path, created["id"], ProbeResult("success", 2.25)
    )

    response = client.get("/api/history?limit=1")
    assert response.status_code == 200
    assert len(response.json()) == 1
    record = response.json()[0]
    assert record["target_name"] == "历史测试入口"
    assert record["ip"] == "192.0.2.55"
    assert record["port"] == 8443
    assert record["protocol"] == "TCP"
    assert record["status"] == "success"
    assert record["latency_ms"] == 2.25


def test_icmp_history_has_no_port_and_clears_failed_latency(
    client: TestClient,
) -> None:
    client.post("/api/auth/login", json={"password": "correct-password"})
    created = client.post(
        "/api/targets",
        json={"name": "ICMP 历史", "ip": "2001:db8::8"},
    ).json()
    database_path = client.app.state.settings.database_path
    record_probe_result(
        database_path,
        created["id"],
        ProbeResult("failure", None, "ICMP Ping 超时"),
    )

    response = client.get("/api/history?limit=1")
    assert response.status_code == 200
    record = response.json()[0]
    assert record["protocol"] == "ICMP"
    assert record["port"] is None
    assert record["status"] == "failure"
    assert record["latency_ms"] is None
