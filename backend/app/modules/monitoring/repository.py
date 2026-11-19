import time
from pathlib import Path
from typing import Any

from app.database import connect
from app.modules.monitoring.probes import ProbeResult
from app.modules.targets.repository import get_target


def record_probe_result(
    database_path: Path, target_id: int, result: ProbeResult
) -> dict[str, Any] | None:
    checked_at = int(time.time())
    with connect(database_path) as connection:
        target = connection.execute(
            "SELECT protocol, consecutive_failures FROM check_targets WHERE id = ?",
            (target_id,),
        ).fetchone()
        if target is None:
            return None

        failures = target["consecutive_failures"]
        if result.outcome == "success":
            status = "normal"
            failures = 0
        elif result.outcome == "failure":
            failures += 1
            if target["protocol"] == "TCP":
                status = "abnormal" if failures >= 3 else "warning"
            else:
                status = "abnormal"
        else:
            status = "unknown"

        connection.execute(
            """
            UPDATE check_targets
            SET status = ?, last_latency_ms = ?, last_checked_at = ?,
                consecutive_failures = ?, last_error = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                result.latency_ms,
                checked_at,
                failures,
                result.message,
                checked_at,
                target_id,
            ),
        )
        connection.execute(
            """
            INSERT INTO check_history(target_id, status, latency_ms, error_message, checked_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                target_id,
                result.outcome,
                result.latency_ms,
                result.message,
                checked_at,
            ),
        )

    return get_target(database_path, target_id)


def list_target_history(
    database_path: Path, target_id: int, limit: int
) -> list[dict[str, Any]]:
    with connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, target_id, status, latency_ms, error_message, checked_at
            FROM check_history
            WHERE target_id = ?
            ORDER BY checked_at DESC, id DESC
            LIMIT ?
            """,
            (target_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def cleanup_old_history(database_path: Path, retention_days: int) -> int:
    cutoff = int(time.time()) - retention_days * 86400
    with connect(database_path) as connection:
        cursor = connection.execute(
            "DELETE FROM check_history WHERE checked_at < ?", (cutoff,)
        )
    return cursor.rowcount
