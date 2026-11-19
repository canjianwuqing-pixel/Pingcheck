import asyncio
import logging
from contextlib import suppress
from typing import Any, Protocol

from app.core.config import Settings
from app.modules.monitoring import probes
from app.modules.monitoring.repository import cleanup_old_history, record_probe_result
from app.modules.targets.repository import get_target, list_enabled_target_ids


logger = logging.getLogger(__name__)


class TargetNotifier(Protocol):
    async def send_target_event(
        self, event: str, target: dict[str, Any]
    ) -> Any: ...


class TargetNotFoundError(Exception):
    pass


class TargetDisabledError(Exception):
    pass


class MonitorService:
    def __init__(
        self, settings: Settings, notifier: TargetNotifier | None = None
    ) -> None:
        self.settings = settings
        self.notifier = notifier
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_checks)
        self._target_locks: dict[int, asyncio.Lock] = {}
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="pingcheck-monitor")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                cleanup_old_history(
                    self.settings.database_path,
                    self.settings.history_retention_days,
                )
                await self.check_enabled_targets()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Scheduled monitoring cycle failed")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.settings.monitor_interval_seconds,
                )
            except TimeoutError:
                continue

    async def check_enabled_targets(self) -> list[dict[str, Any]]:
        target_ids = list_enabled_target_ids(self.settings.database_path)
        results = await asyncio.gather(
            *(self.check_target(target_id) for target_id in target_ids),
            return_exceptions=True,
        )
        completed: list[dict[str, Any]] = []
        for result in results:
            if isinstance(result, dict):
                completed.append(result)
            elif isinstance(result, Exception) and not isinstance(
                result, (TargetNotFoundError, TargetDisabledError)
            ):
                logger.error("Target check failed unexpectedly: %s", result)
        return completed

    async def check_target(self, target_id: int) -> dict[str, Any]:
        lock = self._target_locks.setdefault(target_id, asyncio.Lock())
        async with lock:
            target = get_target(self.settings.database_path, target_id)
            if target is None:
                raise TargetNotFoundError
            if not target["enabled"]:
                raise TargetDisabledError

            async with self._semaphore:
                result = await probes.probe_target(
                    target["protocol"],
                    target["ip"],
                    target["port"],
                    self.settings.detection_timeout_seconds,
                )
            recorded = record_probe_result(
                self.settings.database_path, target_id, result
            )
            if recorded is None:
                raise TargetNotFoundError
            if recorded.notification_event is not None and self.notifier is not None:
                try:
                    await self.notifier.send_target_event(
                        recorded.notification_event, recorded.target
                    )
                except Exception:
                    logger.error(
                        "Telegram notification failed unexpectedly for target %s",
                        target_id,
                    )
            return recorded.target
