import time
from pathlib import Path
from typing import Any

from app.database import connect


def get_telegram_settings(database_path: Path) -> dict[str, Any]:
    with connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT bot_token, chat_id, enabled,
                   proxy_type, proxy_host, proxy_port,
                   proxy_username, proxy_password,
                   ss_server, ss_port, ss_method, ss_password, updated_at
            FROM telegram_settings
            WHERE id = 1
            """
        ).fetchone()
    if row is None:
        return {
            "bot_token": "",
            "chat_id": "",
            "enabled": False,
            "proxy_type": "direct",
            "proxy_host": "",
            "proxy_port": None,
            "proxy_username": "",
            "proxy_password": "",
            "ss_server": "",
            "ss_port": None,
            "ss_method": "aes-256-gcm",
            "ss_password": "",
            "updated_at": None,
        }
    return {
        "bot_token": row["bot_token"],
        "chat_id": row["chat_id"],
        "enabled": bool(row["enabled"]),
        "proxy_type": row["proxy_type"],
        "proxy_host": row["proxy_host"],
        "proxy_port": row["proxy_port"],
        "proxy_username": row["proxy_username"],
        "proxy_password": row["proxy_password"],
        "ss_server": row["ss_server"],
        "ss_port": row["ss_port"],
        "ss_method": row["ss_method"],
        "ss_password": row["ss_password"],
        "updated_at": row["updated_at"],
    }


def save_telegram_settings(
    database_path: Path,
    *,
    bot_token: str | None,
    chat_id: str,
    enabled: bool,
    proxy_type: str = "direct",
    proxy_host: str = "",
    proxy_port: int | None = None,
    proxy_username: str = "",
    proxy_password: str | None = None,
    ss_server: str = "",
    ss_port: int | None = None,
    ss_method: str = "aes-256-gcm",
    ss_password: str | None = None,
) -> dict[str, Any]:
    current = get_telegram_settings(database_path)
    saved_token = current["bot_token"] if bot_token is None else bot_token
    if proxy_type in ("direct", "ss"):
        proxy_host = ""
        proxy_port = None
        proxy_username = ""
        saved_proxy_password = ""
    else:
        saved_proxy_password = (
            current["proxy_password"]
            if proxy_password is None
            else proxy_password
        )
    saved_ss_password = (
        current["ss_password"] if ss_password is None else ss_password
    )
    updated_at = int(time.time())
    with connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO telegram_settings(
                id, bot_token, chat_id, enabled,
                proxy_type, proxy_host, proxy_port,
                proxy_username, proxy_password,
                ss_server, ss_port, ss_method, ss_password, updated_at
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                bot_token = excluded.bot_token,
                chat_id = excluded.chat_id,
                enabled = excluded.enabled,
                proxy_type = excluded.proxy_type,
                proxy_host = excluded.proxy_host,
                proxy_port = excluded.proxy_port,
                proxy_username = excluded.proxy_username,
                proxy_password = excluded.proxy_password,
                ss_server = excluded.ss_server,
                ss_port = excluded.ss_port,
                ss_method = excluded.ss_method,
                ss_password = excluded.ss_password,
                updated_at = excluded.updated_at
            """,
            (
                saved_token,
                chat_id,
                int(enabled),
                proxy_type,
                proxy_host,
                proxy_port,
                proxy_username,
                saved_proxy_password,
                ss_server,
                ss_port,
                ss_method,
                saved_ss_password,
                updated_at,
            ),
        )
    return get_telegram_settings(database_path)
