from datetime import datetime
from pathlib import Path

from kaolalabot.services.scheduler import ScheduledTask, SchedulerService


def test_scheduler_cron_next_run(tmp_path: Path):
    svc = SchedulerService(
        storage_file=tmp_path / "tasks.json",
        log_file=tmp_path / "task_logs.jsonl",
    )
    task = ScheduledTask(
        task_id="",
        name="cron-demo",
        schedule_type="cron",
        cron_expression="*/10 * * * *",
    )
    anchor = datetime(2026, 3, 4, 12, 23, 13)
    next_run = svc._calculate_next_run(task, anchor=anchor)
    assert next_run == datetime(2026, 3, 4, 12, 30, 0)
