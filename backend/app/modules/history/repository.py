from pathlib import Path
from typing import Any

from app.database import connect


def list_recent_history(database_path: Path, limit: int) -> list[dict[str, Any]]:
    with connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT h.id, h.target_id, t.name AS target_name, t.host AS ip,
                   t.port, t.protocol, h.status, h.latency_ms,
                   h.error_message, h.checked_at
            FROM check_history AS h
            JOIN check_targets AS t ON t.id = h.target_id
            ORDER BY h.checked_at DESC, h.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
