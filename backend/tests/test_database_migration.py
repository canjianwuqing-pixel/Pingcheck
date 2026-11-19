import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.database import initialize_database
from app.main import create_app


PHASE_ONE_TARGET_SCHEMA = """
CREATE TABLE check_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    protocol TEXT NOT NULL CHECK (protocol IN ('TCP', 'UDP')),
    host TEXT NOT NULL,
    port INTEGER NOT NULL CHECK (port BETWEEN 1 AND 65535),
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
)
"""


def make_settings(database_path: Path) -> Settings:
    return Settings(
        admin_password_hash=hash_password("migration-password", salt="migration-salt"),
        session_secret="migration-session-secret-long-enough",
        database_path=database_path,
    )


def test_phase_one_database_adds_note_column_without_losing_data(tmp_path: Path) -> None:
    database_path = tmp_path / "phase-one.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(PHASE_ONE_TARGET_SCHEMA)
        connection.execute(
            """
            INSERT INTO check_targets(name, protocol, host, port, enabled, created_at, updated_at)
            VALUES ('旧入口', 'TCP', '192.0.2.20', 443, 1, 1, 1)
            """
        )

    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(check_targets)")
        }
        saved = connection.execute(
            "SELECT name, host, port, note FROM check_targets"
        ).fetchone()

    assert "note" in columns
    assert saved == ("旧入口", "192.0.2.20", 443, "")


def test_target_data_survives_application_restart(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "persistent.db")

    with TestClient(create_app(settings)) as first_client:
        first_client.post(
            "/api/auth/login", json={"password": "migration-password"}
        )
        created = first_client.post(
            "/api/targets",
            json={
                "name": "持久化入口",
                "ip": "198.51.100.8",
                "port": 9000,
                "protocol": "TCP",
                "note": "重启测试",
            },
        )
        assert created.status_code == 201

    with TestClient(create_app(settings)) as restarted_client:
        restarted_client.post(
            "/api/auth/login", json={"password": "migration-password"}
        )
        targets = restarted_client.get("/api/targets")

    assert targets.status_code == 200
    assert len(targets.json()) == 1
    assert targets.json()[0]["name"] == "持久化入口"
