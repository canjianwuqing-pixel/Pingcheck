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
    protocol TEXT NOT NULL CHECK (protocol IN ('TCP', 'UDP')),
    host TEXT NOT NULL,
    port INTEGER NOT NULL CHECK (port BETWEEN 1 AND 65535),
    note TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
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
    updated_at INTEGER NOT NULL
);
"""


def connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


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
