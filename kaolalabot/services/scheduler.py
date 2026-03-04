"""Configurable scheduler service with task CRUD and execution logs."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable

from loguru import logger

TaskRunner = Callable[["ScheduledTask"], Awaitable[str] | str]


@dataclass
class ScheduledTask:
    """A configured scheduled task."""

    task_id: str
    name: str
    enabled: bool = True
    schedule_type: str = "interval"  # interval|daily|weekly|cron
    interval_seconds: int = 60
    daily_time: str = "09:00"
    weekdays: list[int] = field(default_factory=lambda: [0])  # Monday=0
    cron_expression: str = "*/5 * * * *"
    runner: str = "echo"
    payload: dict[str, Any] = field(default_factory=dict)
    next_run_at: str | None = None
    last_run_at: str | None = None


@dataclass
class TaskLogEntry:
    """Task execution log entry."""

    task_id: str
    task_name: str
    run_at: str
    success: bool
    message: str
    duration_ms: int


class SchedulerService:
    """Configurable scheduler with persistent tasks and logs."""

    def __init__(
        self,
        storage_file: Path,
        log_file: Path,
        tick_seconds: float = 1.0,
        max_concurrent_runs: int = 4,
    ):
        self.storage_file = Path(storage_file)
        self.log_file = Path(log_file)
        self.tick_seconds = max(0.2, float(tick_seconds))
        self._semaphore = asyncio.Semaphore(max(1, max_concurrent_runs))
        self._tasks: dict[str, ScheduledTask] = {}
        self._runner_registry: dict[str, TaskRunner] = {}
        self._running = False
        self._main_task: asyncio.Task | None = None

        self.register_runner("echo", self._default_echo_runner)
        self._ensure_paths()
        self._load_tasks()

    async def start(self) -> None:
        self._running = True
        if self._main_task is None or self._main_task.done():
            self._main_task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._main_task:
            self._main_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._main_task

    def register_runner(self, name: str, runner: TaskRunner) -> None:
        self._runner_registry[name] = runner

    def list_tasks(self) -> list[ScheduledTask]:
        return list(self._tasks.values())

    def get_task(self, task_id: str) -> ScheduledTask | None:
        return self._tasks.get(task_id)

    def add_task(self, task: ScheduledTask) -> ScheduledTask:
        if not task.task_id:
            task.task_id = str(uuid.uuid4())
        task.next_run_at = self._calculate_next_run(task).isoformat()
        self._tasks[task.task_id] = task
        self._save_tasks()
        return task

    def update_task(self, task_id: str, data: dict[str, Any]) -> ScheduledTask | None:
        task = self._tasks.get(task_id)
        if not task:
            return None
        for key, value in data.items():
            if hasattr(task, key):
                setattr(task, key, value)
        task.next_run_at = self._calculate_next_run(task).isoformat()
        self._save_tasks()
        return task

    def delete_task(self, task_id: str) -> bool:
        if task_id not in self._tasks:
            return False
        self._tasks.pop(task_id, None)
        self._save_tasks()
        return True

    def enable_task(self, task_id: str, enabled: bool) -> ScheduledTask | None:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.enabled = enabled
        task.next_run_at = self._calculate_next_run(task).isoformat() if enabled else None
        self._save_tasks()
        return task

    def read_logs(self, limit: int = 200) -> list[dict[str, Any]]:
        if not self.log_file.exists():
            return []
        lines = self.log_file.read_text(encoding="utf-8").splitlines()
        rows = [json.loads(line) for line in lines[-max(1, limit) :]]
        return rows

    async def run_task_now(self, task_id: str) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if not task:
            return {"ok": False, "error": "task not found"}
        return await self._run_single_task(task)

    def status(self) -> dict[str, Any]:
        enabled_count = len([t for t in self._tasks.values() if t.enabled])
        return {
            "running": self._running,
            "task_count": len(self._tasks),
            "enabled_task_count": enabled_count,
            "tick_seconds": self.tick_seconds,
            "storage_file": str(self.storage_file),
            "log_file": str(self.log_file),
        }

    async def _loop(self) -> None:
        while self._running:
            now = datetime.now()
            due_tasks = [t for t in self._tasks.values() if self._is_due(t, now)]
            for task in due_tasks:
                asyncio.create_task(self._run_with_limit(task))
            await asyncio.sleep(self.tick_seconds)

    async def _run_with_limit(self, task: ScheduledTask) -> None:
        async with self._semaphore:
            await self._run_single_task(task)

    async def _run_single_task(self, task: ScheduledTask) -> dict[str, Any]:
        start = datetime.now()
        runner = self._runner_registry.get(task.runner)
        if runner is None:
            result = {"ok": False, "error": f"runner not found: {task.runner}"}
            await self._write_log(task, start, result, 0)
            return result

        try:
            output = runner(task)
            if asyncio.iscoroutine(output):
                output = await output
            result = {"ok": True, "result": output if output is not None else ""}
        except Exception as exc:
            logger.warning("Scheduler task {} failed: {}", task.task_id, exc)
            result = {"ok": False, "error": str(exc)}

        end = datetime.now()
        task.last_run_at = start.isoformat()
        task.next_run_at = self._calculate_next_run(task, anchor=end).isoformat() if task.enabled else None
        self._save_tasks()
        await self._write_log(
            task,
            start,
            result,
            int((end - start).total_seconds() * 1000),
        )
        return result

    async def _write_log(
        self,
        task: ScheduledTask,
        run_at: datetime,
        result: dict[str, Any],
        duration_ms: int,
    ) -> None:
        entry = TaskLogEntry(
            task_id=task.task_id,
            task_name=task.name,
            run_at=run_at.isoformat(),
            success=bool(result.get("ok")),
            message=str(result.get("result") or result.get("error") or ""),
            duration_ms=duration_ms,
        )
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

    def _is_due(self, task: ScheduledTask, now: datetime) -> bool:
        if not task.enabled or not task.next_run_at:
            return False
        try:
            due_at = datetime.fromisoformat(task.next_run_at)
        except ValueError:
            due_at = self._calculate_next_run(task)
            task.next_run_at = due_at.isoformat()
            self._save_tasks()
        return now >= due_at

    def _calculate_next_run(self, task: ScheduledTask, anchor: datetime | None = None) -> datetime:
        now = anchor or datetime.now()
        if task.schedule_type == "cron":
            try:
                return _next_cron_run(task.cron_expression, now)
            except Exception as exc:
                logger.warning("Invalid cron expression for task {}: {} ({})", task.task_id, task.cron_expression, exc)
                return now + timedelta(minutes=5)
        if task.schedule_type == "daily":
            hour, minute = _parse_hhmm(task.daily_time)
            candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate <= now:
                candidate += timedelta(days=1)
            return candidate
        if task.schedule_type == "weekly":
            weekdays = sorted(set(task.weekdays or [0]))
            hour, minute = _parse_hhmm(task.daily_time)
            for offset in range(0, 8):
                candidate = now + timedelta(days=offset)
                if candidate.weekday() in weekdays:
                    run_at = candidate.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if run_at > now:
                        return run_at
            return (now + timedelta(days=7)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        # interval default
        interval = max(1, int(task.interval_seconds))
        return now + timedelta(seconds=interval)

    async def _default_echo_runner(self, task: ScheduledTask) -> str:
        return f"scheduled task executed: {task.name}"

    def _ensure_paths(self) -> None:
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_tasks(self) -> None:
        if not self.storage_file.exists():
            return
        try:
            data = json.loads(self.storage_file.read_text(encoding="utf-8"))
            self._tasks = {
                row["task_id"]: ScheduledTask(**row)
                for row in data
                if isinstance(row, dict) and row.get("task_id")
            }
        except Exception as exc:
            logger.warning("Scheduler task load failed: {}", exc)
            self._tasks = {}

    def _save_tasks(self) -> None:
        rows = [asdict(task) for task in self._tasks.values()]
        self.storage_file.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _parse_hhmm(value: str) -> tuple[int, int]:
    try:
        hour_s, minute_s = value.strip().split(":", 1)
        hour = min(23, max(0, int(hour_s)))
        minute = min(59, max(0, int(minute_s)))
        return hour, minute
    except Exception:
        return 9, 0


def _next_cron_run(expr: str, anchor: datetime) -> datetime:
    fields = expr.strip().split()
    if len(fields) != 5:
        raise ValueError("cron expression must have 5 fields: m h dom mon dow")

    minutes = _parse_cron_field(fields[0], 0, 59)
    hours = _parse_cron_field(fields[1], 0, 23)
    dom = _parse_cron_field(fields[2], 1, 31)
    months = _parse_cron_field(fields[3], 1, 12)
    dow = _parse_cron_field(fields[4], 0, 7)
    if 7 in dow:
        dow = set(dow)
        dow.add(0)

    candidate = (anchor + timedelta(minutes=1)).replace(second=0, microsecond=0)
    for _ in range(60 * 24 * 366):
        cron_weekday = (candidate.weekday() + 1) % 7  # Monday=1 ... Sunday=0
        if (
            candidate.minute in minutes
            and candidate.hour in hours
            and candidate.day in dom
            and candidate.month in months
            and cron_weekday in dow
        ):
            return candidate
        candidate += timedelta(minutes=1)
    raise ValueError("no matching run time found in 366 days")


def _parse_cron_field(value: str, min_value: int, max_value: int) -> set[int]:
    allowed: set[int] = set()
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        if token == "*":
            allowed.update(range(min_value, max_value + 1))
            continue
        if token.startswith("*/"):
            step = max(1, int(token[2:]))
            allowed.update(range(min_value, max_value + 1, step))
            continue
        if "-" in token:
            start_s, end_s = token.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            if start > end:
                start, end = end, start
            for num in range(start, end + 1):
                if min_value <= num <= max_value:
                    allowed.add(num)
            continue
        num = int(token)
        if min_value <= num <= max_value:
            allowed.add(num)
    if not allowed:
        raise ValueError(f"invalid cron field: {value}")
    return allowed


import contextlib
