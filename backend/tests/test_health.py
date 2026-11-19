import sqlite3

from fastapi.testclient import TestClient


def test_health_and_reserved_schema(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.1.0",
        "database": "ok",
    }

    database_path = client.app.state.settings.database_path
    with sqlite3.connect(database_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {
        "sessions",
        "check_targets",
        "check_history",
        "telegram_settings",
    }.issubset(table_names)
