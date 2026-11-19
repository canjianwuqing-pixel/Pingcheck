import time
from pathlib import Path
from typing import Any

from app.database import connect


def get_telegram_settings(database_path: Path) -> dict[str, Any]:
    with connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT bot_token, chat_id, enabled, updated_at
            FROM telegram_settings
            WHERE id = 1
            """
        ).fetchone()
    if row is None:
        return {
            "bot_token": "",
            "chat_id": "",
            "enabled": False,
            "updated_at": None,
        }
    return {
        "bot_token": row["bot_token"],
        "chat_id": row["chat_id"],
        "enabled": bool(row["enabled"]),
        "updated_at": row["updated_at"],
    }


def save_telegram_settings(
    database_path: Path,
    *,
    bot_token: str | None,
    chat_id: str,
    enabled: bool,
) -> dict[str, Any]:
    current = get_telegram_settings(database_path)
    saved_token = current["bot_token"] if bot_token is None else bot_token
    updated_at = int(time.time())
    with connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO telegram_settings(id, bot_token, chat_id, enabled, updated_at)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                bot_token = excluded.bot_token,
                chat_id = excluded.chat_id,
                enabled = excluded.enabled,
                updated_at = excluded.updated_at
            """,
            (saved_token, chat_id, int(enabled), updated_at),
        )
    return get_telegram_settings(database_path)
