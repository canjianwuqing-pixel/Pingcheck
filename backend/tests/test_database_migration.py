import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.database import initialize_database
from app.main import create_app
from app.modules.monitoring.probes import ProbeResult
from app.modules.monitoring.repository import record_probe_result
from app.modules.targets.repository import update_target_enabled


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
            """
            SELECT name, host, port, note, status, last_latency_ms,
                   last_checked_at, consecutive_failures, last_error, alert_active
            FROM check_targets
            """
        ).fetchone()

    assert {
        "note",
        "status",
        "last_latency_ms",
        "last_checked_at",
        "consecutive_failures",
        "last_error",
        "alert_active",
    }.issubset(columns)
    assert saved == (
        "旧入口",
        "192.0.2.20",
        443,
        "",
        "pending",
        None,
        None,
        0,
        None,
        0,
    )


def test_existing_telegram_settings_gain_proxy_columns(tmp_path: Path) -> None:
    database_path = tmp_path / "phase-four.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE telegram_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                bot_token TEXT NOT NULL DEFAULT '',
                chat_id TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO telegram_settings(
                id, bot_token, chat_id, enabled, updated_at
            ) VALUES (1, 'existing-token', '-100123', 1, 123)
            """
        )

    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(telegram_settings)")
        }
        saved = connection.execute(
            """
            SELECT bot_token, chat_id, enabled, proxy_type, proxy_host,
                   proxy_port, proxy_username, proxy_password, updated_at
            FROM telegram_settings WHERE id = 1
            """
        ).fetchone()

    assert {
        "proxy_type",
        "proxy_host",
        "proxy_port",
        "proxy_username",
        "proxy_password",
    }.issubset(columns)
    assert saved == (
        "existing-token",
        "-100123",
        1,
        "direct",
        "",
        None,
        "",
        "",
        123,
    )


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
        target_id = created.json()["id"]

    record_probe_result(
        settings.database_path, target_id, ProbeResult("success", 2.5)
    )
    update_target_enabled(settings.database_path, target_id, False)

    with TestClient(create_app(settings)) as restarted_client:
        restarted_client.post(
            "/api/auth/login", json={"password": "migration-password"}
        )
        targets = restarted_client.get("/api/targets")
        history = restarted_client.get(f"/api/targets/{target_id}/history")

    assert targets.status_code == 200
    assert len(targets.json()) == 1
    assert targets.json()[0]["name"] == "持久化入口"
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["status"] == "success"
