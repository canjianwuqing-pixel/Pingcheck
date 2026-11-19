from fastapi.testclient import TestClient


def test_login_session_and_logout(client: TestClient) -> None:
    before_login = client.get("/api/auth/me")
    assert before_login.status_code == 401

    wrong_password = client.post(
        "/api/auth/login", json={"password": "wrong-password"}
    )
    assert wrong_password.status_code == 401
    assert wrong_password.json()["detail"] == "管理密码错误"

    login = client.post(
        "/api/auth/login", json={"password": "correct-password"}
    )
    assert login.status_code == 200
    assert login.json() == {"authenticated": True}
    assert login.cookies.get("pingcheck_session")

    current_admin = client.get("/api/auth/me")
    assert current_admin.status_code == 200
    assert current_admin.json() == {"authenticated": True}

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert logout.json() == {"authenticated": False}
    assert client.get("/api/auth/me").status_code == 401


def test_login_rejects_empty_password(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"password": ""})
    assert response.status_code == 422
