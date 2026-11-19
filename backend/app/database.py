import sqlite3
import time
from pathlib import Path

from app.core.security import digest_session_token


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS check_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    protocol TEXT NOT NULL CHECK (protocol IN ('ICMP', 'TCP', 'UDP')),
    host TEXT NOT NULL,
    port INTEGER,
    note TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'pending',
    last_latency_ms REAL,
    last_checked_at INTEGER,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    alert_active INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    CHECK (
        (protocol = 'ICMP' AND port IS NULL)
        OR (
            protocol IN ('TCP', 'UDP')
            AND port IS NOT NULL
            AND port BETWEEN 1 AND 65535
        )
    )
);

CREATE TABLE IF NOT EXISTS check_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    latency_ms REAL,
    error_message TEXT,
    checked_at INTEGER NOT NULL,
    FOREIGN KEY (target_id) REFERENCES check_targets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_check_history_target_time
    ON check_history(target_id, checked_at DESC);

CREATE TABLE IF NOT EXISTS telegram_settings (
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
);
"""


def connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _migrate_targets_for_icmp(connection: sqlite3.Connection) -> None:
    table = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'check_targets'"
    ).fetchone()
    table_sql = table["sql"] if table is not None else ""
    if table is None or (
        "'ICMP'" in (table_sql or "")
        and "port IS NOT NULL" in (table_sql or "")
    ):
        return

    connection.commit()
    connection.execute("PRAGMA foreign_keys=OFF")
    try:
        connection.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE check_targets_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                protocol TEXT NOT NULL CHECK (protocol IN ('ICMP', 'TCP', 'UDP')),
                host TEXT NOT NULL,
                port INTEGER,
                note TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'pending',
                last_latency_ms REAL,
                last_checked_at INTEGER,
                consecutive_failures INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                alert_active INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                CHECK (
                    (protocol = 'ICMP' AND port IS NULL)
                    OR (
                        protocol IN ('TCP', 'UDP')
                        AND port IS NOT NULL
                        AND port BETWEEN 1 AND 65535
                    )
                )
            );
            INSERT INTO check_targets_new(
                id, name, protocol, host, port, note, enabled, status,
                last_latency_ms, last_checked_at, consecutive_failures,
                last_error, alert_active, created_at, updated_at
            )
            SELECT
                id, name, protocol, host, port, note, enabled, status,
                last_latency_ms, last_checked_at, consecutive_failures,
                last_error, alert_active, created_at, updated_at
            FROM check_targets;
            DROP TABLE check_targets;
            ALTER TABLE check_targets_new RENAME TO check_targets;
            COMMIT;
            """
        )
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys=ON")

    violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise sqlite3.IntegrityError("ICMP migration failed foreign key check")


def initialize_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(database_path) as connection:
        connection.executescript(SCHEMA)
        target_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(check_targets)").fetchall()
        }
        if "note" not in target_columns:
            connection.execute(
                "ALTER TABLE check_targets ADD COLUMN note TEXT NOT NULL DEFAULT ''"
            )
        monitoring_columns = {
            "status": "TEXT NOT NULL DEFAULT 'pending'",
            "last_latency_ms": "REAL",
            "last_checked_at": "INTEGER",
            "consecutive_failures": "INTEGER NOT NULL DEFAULT 0",
            "last_error": "TEXT",
            "alert_active": "INTEGER NOT NULL DEFAULT 0",
        }
        for column_name, definition in monitoring_columns.items():
            if column_name not in target_columns:
                connection.execute(
                    f"ALTER TABLE check_targets ADD COLUMN {column_name} {definition}"
                )
        _migrate_targets_for_icmp(connection)
        telegram_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(telegram_settings)"
            ).fetchall()
        }
        proxy_columns = {
            "proxy_type": "TEXT NOT NULL DEFAULT 'direct'",
            "proxy_host": "TEXT NOT NULL DEFAULT ''",
            "proxy_port": "INTEGER",
            "proxy_username": "TEXT NOT NULL DEFAULT ''",
            "proxy_password": "TEXT NOT NULL DEFAULT ''",
        }
        for column_name, definition in proxy_columns.items():
            if column_name not in telegram_columns:
                connection.execute(
                    f"ALTER TABLE telegram_settings ADD COLUMN {column_name} {definition}"
                )
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (int(time.time()),))


def database_is_ready(database_path: Path) -> bool:
    try:
        with connect(database_path) as connection:
            return connection.execute("SELECT 1").fetchone()[0] == 1
    except sqlite3.Error:
        return False


def create_session(
    database_path: Path, secret: str, max_age_seconds: int
) -> tuple[str, int]:
    import secrets

    token = secrets.token_urlsafe(32)
    now = int(time.time())
    expires_at = now + max_age_seconds
    token_hash = digest_session_token(token, secret)
    with connect(database_path) as connection:
        connection.execute(
            "INSERT INTO sessions(token_hash, created_at, expires_at) VALUES (?, ?, ?)",
            (token_hash, now, expires_at),
        )
    return token, expires_at


def session_is_valid(database_path: Path, secret: str, token: str) -> bool:
    token_hash = digest_session_token(token, secret)
    now = int(time.time())
    with connect(database_path) as connection:
        row = connection.execute(
            "SELECT expires_at FROM sessions WHERE token_hash = ?", (token_hash,)
        ).fetchone()
        if row is None:
            return False
        if row["expires_at"] <= now:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
            return False
        return True


def delete_session(database_path: Path, secret: str, token: str) -> None:
    token_hash = digest_session_token(token, secret)
    with connect(database_path) as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
