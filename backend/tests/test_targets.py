from fastapi.testclient import TestClient


def login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"password": "correct-password"}
    )
    assert response.status_code == 200


def test_target_endpoints_require_login(client: TestClient) -> None:
    assert client.get("/api/targets").status_code == 401
    assert (
        client.post(
            "/api/targets",
            json={
                "name": "Web",
                "ip": "127.0.0.1",
                "port": 80,
                "protocol": "TCP",
                "note": "",
            },
        ).status_code
        == 401
    )


def test_target_crud_and_enabled_state(client: TestClient) -> None:
    login(client)

    created = client.post(
        "/api/targets",
        json={
            "name": " 主站 ",
            "ip": "192.0.2.10",
            "port": 443,
            "protocol": "tcp",
            "note": " HTTPS 入口 ",
        },
    )
    assert created.status_code == 201
    target = created.json()
    assert target["name"] == "主站"
    assert target["protocol"] == "TCP"
    assert target["note"] == "HTTPS 入口"
    assert target["enabled"] is True

    target_id = target["id"]
    updated = client.put(
        f"/api/targets/{target_id}",
        json={
            "name": "主站 HTTPS",
            "ip": "192.0.2.10",
            "port": 8443,
            "protocol": "TCP",
            "note": "备用端口",
            "enabled": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["port"] == 8443

    paused = client.patch(
        f"/api/targets/{target_id}/enabled", json={"enabled": False}
    )
    assert paused.status_code == 200
    assert paused.json()["enabled"] is False

    listed = client.get("/api/targets")
    assert listed.status_code == 200
    assert listed.json() == [paused.json()]

    removed = client.delete(f"/api/targets/{target_id}")
    assert removed.status_code == 204
    assert client.get("/api/targets").json() == []
    assert client.delete(f"/api/targets/{target_id}").status_code == 404


def test_icmp_is_default_and_does_not_use_port(client: TestClient) -> None:
    login(client)
    created = client.post(
        "/api/targets",
        json={"name": "默认 Ping", "ip": "2001:db8::20", "note": ""},
    )
    assert created.status_code == 201
    assert created.json()["protocol"] == "ICMP"
    assert created.json()["port"] is None

    updated = client.put(
        f"/api/targets/{created.json()['id']}",
        json={
            "name": "IPv4 Ping",
            "ip": "192.0.2.20",
            "protocol": "icmp",
            "port": 443,
            "note": "ICMP 忽略端口",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["port"] is None
    assert updated.json()["protocol"] == "ICMP"


def test_same_ip_supports_different_ports_and_protocols(client: TestClient) -> None:
    login(client)
    entries = [
        (None, "ICMP"),
        (53, "UDP"),
        (53, "TCP"),
        (853, "TCP"),
    ]

    for port, protocol in entries:
        response = client.post(
            "/api/targets",
            json={
                "name": f"DNS {protocol} {port}",
                "ip": "2001:db8::1",
                "port": port,
                "protocol": protocol,
                "note": "",
            },
        )
        assert response.status_code == 201

    targets = client.get("/api/targets").json()
    assert len(targets) == 4
    assert {(target["port"], target["protocol"]) for target in targets} == set(entries)


def test_target_validation(client: TestClient) -> None:
    login(client)
    base = {
        "name": "测试入口",
        "ip": "192.0.2.1",
        "port": 80,
        "protocol": "TCP",
        "note": "",
    }

    assert client.post("/api/targets", json={**base, "ip": "not-an-ip"}).status_code == 422
    assert client.post("/api/targets", json={**base, "port": 0}).status_code == 422
    assert client.post("/api/targets", json={**base, "port": 65536}).status_code == 422
    assert client.post("/api/targets", json={**base, "protocol": "HTTP"}).status_code == 422
    without_port = {key: value for key, value in base.items() if key != "port"}
    assert client.post("/api/targets", json=without_port).status_code == 422
