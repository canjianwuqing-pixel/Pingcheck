import time
from pathlib import Path
from typing import Any

from app.database import connect
from app.modules.targets.schemas import TargetWrite


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "ip": row["host"],
        "port": row["port"],
        "protocol": row["protocol"],
        "note": row["note"],
        "enabled": bool(row["enabled"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_targets(database_path: Path) -> list[dict[str, Any]]:
    with connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, name, host, port, protocol, note, enabled, created_at, updated_at
            FROM check_targets
            ORDER BY id DESC
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_target(database_path: Path, target_id: int) -> dict[str, Any] | None:
    with connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT id, name, host, port, protocol, note, enabled, created_at, updated_at
            FROM check_targets
            WHERE id = ?
            """,
            (target_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def create_target(database_path: Path, target: TargetWrite) -> dict[str, Any]:
    now = int(time.time())
    with connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO check_targets(name, host, port, protocol, note, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target.name,
                target.ip,
                target.port,
                target.protocol,
                target.note,
                int(target.enabled),
                now,
                now,
            ),
        )
        target_id = cursor.lastrowid
    return get_target(database_path, target_id)  # type: ignore[return-value]


def update_target(
    database_path: Path, target_id: int, target: TargetWrite
) -> dict[str, Any] | None:
    now = int(time.time())
    with connect(database_path) as connection:
        cursor = connection.execute(
            """
            UPDATE check_targets
            SET name = ?, host = ?, port = ?, protocol = ?, note = ?, enabled = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                target.name,
                target.ip,
                target.port,
                target.protocol,
                target.note,
                int(target.enabled),
                now,
                target_id,
            ),
        )
        if cursor.rowcount == 0:
            return None
    return get_target(database_path, target_id)


def update_target_enabled(
    database_path: Path, target_id: int, enabled: bool
) -> dict[str, Any] | None:
    with connect(database_path) as connection:
        cursor = connection.execute(
            "UPDATE check_targets SET enabled = ?, updated_at = ? WHERE id = ?",
            (int(enabled), int(time.time()), target_id),
        )
        if cursor.rowcount == 0:
            return None
    return get_target(database_path, target_id)


def delete_target(database_path: Path, target_id: int) -> bool:
    with connect(database_path) as connection:
        cursor = connection.execute(
            "DELETE FROM check_targets WHERE id = ?", (target_id,)
        )
    return cursor.rowcount > 0
