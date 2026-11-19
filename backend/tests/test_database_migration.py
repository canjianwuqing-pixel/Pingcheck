import sqlite3
from pathlib import Path

import pytest
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


PHASE_SIX_TARGET_SCHEMA = """
CREATE TABLE check_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    protocol TEXT NOT NULL CHECK (protocol IN ('TCP', 'UDP')),
    host TEXT NOT NULL,
    port INTEGER NOT NULL CHECK (port BETWEEN 1 AND 65535),
    note TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'pending',
    last_latency_ms REAL,
    last_checked_at INTEGER,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    alert_active INTEGER NOT NULL DEFAULT 0,
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
                   proxy_port, proxy_username, proxy_password,
                   ss_server, ss_port, ss_method, ss_password, updated_at
            FROM telegram_settings WHERE id = 1
            """
        ).fetchone()

    assert {
        "proxy_type",
        "proxy_host",
        "proxy_port",
        "proxy_username",
        "proxy_password",
        "ss_server",
        "ss_port",
        "ss_method",
        "ss_password",
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
        "",
        None,
        "aes-256-gcm",
        "",
        123,
    )


def test_phase_six_database_migrates_icmp_without_losing_data(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "phase-six.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(PHASE_SIX_TARGET_SCHEMA)
        connection.execute(
            """
            CREATE TABLE check_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                latency_ms REAL,
                error_message TEXT,
                checked_at INTEGER NOT NULL,
                FOREIGN KEY (target_id) REFERENCES check_targets(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE telegram_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                bot_token TEXT NOT NULL DEFAULT '',
                chat_id TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 0,
                proxy_type TEXT NOT NULL DEFAULT 'direct',
                proxy_host TEXT NOT NULL DEFAULT '',
                proxy_port INTEGER,
                proxy_username TEXT NOT NULL DEFAULT '',
                proxy_password TEXT NOT NULL DEFAULT '',
                updated_at INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO check_targets(
                id, name, protocol, host, port, note, enabled, status,
                last_latency_ms, last_checked_at, consecutive_failures,
                last_error, alert_active, created_at, updated_at
            ) VALUES (
                7, '现有 TCP', 'TCP', '192.0.2.7', 443, '保留数据', 1,
                'abnormal', NULL, 100, 3, '连接超时', 1, 10, 100
            )
            """
        )
        connection.execute(
            """
            INSERT INTO check_history(
                id, target_id, status, latency_ms, error_message, checked_at
            ) VALUES (9, 7, 'failure', NULL, '连接超时', 100)
            """
        )
        connection.execute(
            """
            INSERT INTO telegram_settings(
                id, bot_token, chat_id, enabled, proxy_type, proxy_host,
                proxy_port, proxy_username, proxy_password, updated_at
            ) VALUES (
                1, 'existing-token', '-1007', 1, 'socks5', 'proxy.local',
                1080, 'user', 'password', 100
            )
            """
        )

    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        target = connection.execute(
            """
            SELECT id, name, protocol, host, port, note, status,
                   consecutive_failures, alert_active
            FROM check_targets WHERE id = 7
            """
        ).fetchone()
        history = connection.execute(
            "SELECT id, target_id, status FROM check_history WHERE id = 9"
        ).fetchone()
        telegram = connection.execute(
            """
            SELECT bot_token, chat_id, proxy_type, proxy_host, proxy_port,
                   proxy_username, proxy_password,
                   ss_server, ss_port, ss_method, ss_password
            FROM telegram_settings WHERE id = 1
            """
        ).fetchone()
        table_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'check_targets'"
        ).fetchone()[0]
        foreign_key_violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
        connection.execute(
            """
            INSERT INTO check_targets(
                name, protocol, host, port, created_at, updated_at
            ) VALUES ('新 ICMP', 'ICMP', '2001:db8::7', NULL, 200, 200)
            """
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO check_targets(
                    name, protocol, host, port, created_at, updated_at
                ) VALUES ('无端口 TCP', 'TCP', '192.0.2.8', NULL, 200, 200)
                """
            )

    assert target == (
        7,
        "现有 TCP",
        "TCP",
        "192.0.2.7",
        443,
        "保留数据",
        "abnormal",
        3,
        1,
    )
    assert history == (9, 7, "failure")
    assert telegram == (
        "existing-token",
        "-1007",
        "socks5",
        "proxy.local",
        1080,
        "user",
        "password",
        "",
        None,
        "aes-256-gcm",
        "",
    )
    assert "'ICMP'" in table_sql
    assert "port IS NOT NULL" in table_sql
    assert foreign_key_violations == []


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
