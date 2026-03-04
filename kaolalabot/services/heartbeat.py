"""Heartbeat service for health reporting and anomaly handling."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Awaitable, Callable

from loguru import logger

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

AlertHandler = Callable[[dict[str, Any]], Awaitable[None] | None]
RestartHandler = Callable[[], Awaitable[None] | None]


class HeartbeatService:
    """Periodic health reporter."""

    def __init__(
        self,
        endpoint: str,
        interval_seconds: int = 30,
        timeout_seconds: int = 10,
        max_failures_before_alert: int = 3,
        auto_restart_on_failure: bool = False,
        include_resource_usage: bool = True,
        health_provider: Callable[[], dict[str, Any]] | None = None,
        alert_handler: AlertHandler | None = None,
        restart_handler: RestartHandler | None = None,
    ):
        self.endpoint = endpoint
        self.interval_seconds = max(5, int(interval_seconds))
        self.timeout_seconds = max(3, int(timeout_seconds))
        self.max_failures_before_alert = max(1, int(max_failures_before_alert))
        self.auto_restart_on_failure = auto_restart_on_failure
        self.include_resource_usage = include_resource_usage
        self.health_provider = health_provider or (lambda: {})
        self.alert_handler = alert_handler
        self.restart_handler = restart_handler

        self._running = False
        self._task: asyncio.Task | None = None
        self._session: aiohttp.ClientSession | None = None
        self._failure_count = 0
        self._last_error: str | None = None
        self._last_success_at: str | None = None

    async def start(self) -> None:
        if not self.endpoint:
            logger.info("Heartbeat disabled: endpoint is empty")
            return
        if not AIOHTTP_AVAILABLE:
            logger.warning("Heartbeat requires aiohttp")
            return
        self._running = True
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds))
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    def status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "endpoint": self.endpoint,
            "failure_count": self._failure_count,
            "last_error": self._last_error,
            "last_success_at": self._last_success_at,
        }

    def build_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "status": "running",
            "health": self.health_provider(),
        }
        if self.include_resource_usage:
            payload["resources"] = self._collect_resources()
        return payload

    async def _loop(self) -> None:
        while self._running:
            outcome = await self.send_once()
            if not outcome.get("ok") and self._failure_count >= self.max_failures_before_alert:
                await self._on_failure_threshold(outcome.get("payload") or {})
            await asyncio.sleep(self.interval_seconds)

    async def send_once(self) -> dict[str, Any]:
        """Send one heartbeat payload immediately."""
        payload = self.build_payload()
        ok = await self._post_payload(payload)
        if ok:
            self._failure_count = 0
            self._last_error = None
            self._last_success_at = datetime.now().isoformat()
            return {"ok": True, "payload": payload}
        self._failure_count += 1
        return {"ok": False, "payload": payload, "error": self._last_error}

    async def _post_payload(self, payload: dict[str, Any]) -> bool:
        if not self._session:
            return False
        try:
            async with self._session.post(self.endpoint, json=payload) as resp:
                if 200 <= resp.status < 300:
                    return True
                self._last_error = f"heartbeat http status={resp.status}"
                return False
        except Exception as exc:
            self._last_error = str(exc)
            logger.warning("Heartbeat post failed: {}", exc)
            return False

    async def _on_failure_threshold(self, payload: dict[str, Any]) -> None:
        logger.warning("Heartbeat failure threshold reached: {}", self._failure_count)
        if self.alert_handler:
            result = self.alert_handler(
                {
                    "failure_count": self._failure_count,
                    "last_error": self._last_error,
                    "payload": payload,
                }
            )
            if asyncio.iscoroutine(result):
                await result

        if self.auto_restart_on_failure and self.restart_handler:
            result = self.restart_handler()
            if asyncio.iscoroutine(result):
                await result

    def _collect_resources(self) -> dict[str, Any]:
        if not PSUTIL_AVAILABLE:
            return {"available": False}
        proc = psutil.Process()
        mem = proc.memory_info()
        return {
            "available": True,
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": psutil.virtual_memory().percent,
            "process_rss": mem.rss,
            "process_threads": proc.num_threads(),
        }


import contextlib
