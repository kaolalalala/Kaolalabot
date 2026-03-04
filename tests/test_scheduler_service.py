from pathlib import Path

import pytest

from kaolalabot.services.scheduler import ScheduledTask, SchedulerService


@pytest.mark.asyncio
async def test_scheduler_add_and_run_task(tmp_path: Path):
    storage = tmp_path / 'tasks.json'
    logs = tmp_path / 'task_logs.jsonl'
    svc = SchedulerService(storage_file=storage, log_file=logs, tick_seconds=0.2)

    async def runner(task):
        return f"ran:{task.name}"

    svc.register_runner('custom', runner)
    task = ScheduledTask(task_id='', name='demo', schedule_type='interval', interval_seconds=60, runner='custom')
    created = svc.add_task(task)
    result = await svc.run_task_now(created.task_id)

    assert result['ok'] is True
    rows = svc.read_logs()
    assert len(rows) >= 1
    assert rows[-1]['task_name'] == 'demo'
