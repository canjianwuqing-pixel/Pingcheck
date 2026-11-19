import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app.database import connect
from app.modules.monitoring.probes import ProbeResult
from app.modules.targets.repository import get_target


NotificationEvent = Literal["alert", "recovery"]


@dataclass(frozen=True)
class RecordedProbe:
    target: dict[str, Any]
    notification_event: NotificationEvent | None


def record_probe_result(
    database_path: Path, target_id: int, result: ProbeResult
) -> RecordedProbe | None:
    checked_at = int(time.time())
    with connect(database_path) as connection:
        target = connection.execute(
            """
            SELECT protocol, consecutive_failures, alert_active
            FROM check_targets
            WHERE id = ?
            """,
            (target_id,),
        ).fetchone()
        if target is None:
            return None

        failures = target["consecutive_failures"]
        alert_active = bool(target["alert_active"])
        notification_event: NotificationEvent | None = None
        if result.outcome == "success":
            status = "normal"
            failures = 0
            if target["protocol"] in ("TCP", "ICMP") and alert_active:
                alert_active = False
                notification_event = "recovery"
        elif result.outcome == "failure":
            failures += 1
            if target["protocol"] in ("TCP", "ICMP"):
                status = "abnormal" if failures >= 3 else "warning"
                if status == "abnormal" and not alert_active:
                    alert_active = True
                    notification_event = "alert"
            else:
                status = "abnormal"
                alert_active = False
        else:
            status = "unknown"
            if target["protocol"] == "UDP":
                alert_active = False

        connection.execute(
            """
            UPDATE check_targets
            SET status = ?, last_latency_ms = ?, last_checked_at = ?,
                consecutive_failures = ?, last_error = ?, updated_at = ?,
                alert_active = ?
            WHERE id = ?
            """,
            (
                status,
                result.latency_ms,
                checked_at,
                failures,
                result.message,
                checked_at,
                int(alert_active),
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

    updated_target = get_target(database_path, target_id)
    if updated_target is None:
        return None
    return RecordedProbe(updated_target, notification_event)


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
