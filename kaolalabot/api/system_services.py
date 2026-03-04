"""System service APIs: MCP, Scheduler, Heartbeat, Clawhub."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from kaolalabot.services.runtime import get_runtime_services
from kaolalabot.services.scheduler import ScheduledTask

router = APIRouter(prefix="/system", tags=["system"])


class MCPCommandRequest(BaseModel):
    command: str


class SchedulerTaskRequest(BaseModel):
    name: str
    enabled: bool = True
    schedule_type: str = "interval"
    interval_seconds: int = 60
    daily_time: str = "09:00"
    weekdays: list[int] = Field(default_factory=lambda: [0])
    cron_expression: str = "*/5 * * * *"
    runner: str = "echo"
    payload: dict[str, Any] = Field(default_factory=dict)


class SkillInvokeRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


class OpenClawInvokeRequest(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    action: str | None = None
    session_key: str | None = None


@router.get("/mcp/status")
async def mcp_status():
    services = get_runtime_services()
    if not services.mcp:
        return {"enabled": False}
    return {"enabled": True, **services.mcp.status()}


@router.post("/mcp/command")
async def mcp_command(req: MCPCommandRequest):
    services = get_runtime_services()
    if not services.mcp:
        raise HTTPException(status_code=404, detail="mcp service not enabled")
    return await services.mcp.execute_command(req.command)


@router.get("/scheduler/status")
async def scheduler_status():
    services = get_runtime_services()
    if not services.scheduler:
        return {"enabled": False}
    return {"enabled": True, **services.scheduler.status()}


@router.get("/scheduler/tasks")
async def scheduler_list_tasks():
    services = get_runtime_services()
    if not services.scheduler:
        raise HTTPException(status_code=404, detail="scheduler service not enabled")
    return {"tasks": [asdict(t) for t in services.scheduler.list_tasks()]}


@router.post("/scheduler/tasks")
async def scheduler_add_task(req: SchedulerTaskRequest):
    services = get_runtime_services()
    if not services.scheduler:
        raise HTTPException(status_code=404, detail="scheduler service not enabled")
    task = ScheduledTask(task_id="", **req.model_dump())
    created = services.scheduler.add_task(task)
    return {"task": asdict(created)}


@router.put("/scheduler/tasks/{task_id}")
async def scheduler_update_task(task_id: str, req: SchedulerTaskRequest):
    services = get_runtime_services()
    if not services.scheduler:
        raise HTTPException(status_code=404, detail="scheduler service not enabled")
    updated = services.scheduler.update_task(task_id, req.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="task not found")
    return {"task": asdict(updated)}


@router.delete("/scheduler/tasks/{task_id}")
async def scheduler_delete_task(task_id: str):
    services = get_runtime_services()
    if not services.scheduler:
        raise HTTPException(status_code=404, detail="scheduler service not enabled")
    ok = services.scheduler.delete_task(task_id)
    return {"ok": ok}


@router.post("/scheduler/tasks/{task_id}/enable")
async def scheduler_enable_task(task_id: str):
    services = get_runtime_services()
    if not services.scheduler:
        raise HTTPException(status_code=404, detail="scheduler service not enabled")
    task = services.scheduler.enable_task(task_id, True)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return {"task": asdict(task)}


@router.post("/scheduler/tasks/{task_id}/disable")
async def scheduler_disable_task(task_id: str):
    services = get_runtime_services()
    if not services.scheduler:
        raise HTTPException(status_code=404, detail="scheduler service not enabled")
    task = services.scheduler.enable_task(task_id, False)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return {"task": asdict(task)}


@router.post("/scheduler/tasks/{task_id}/run")
async def scheduler_run_task(task_id: str):
    services = get_runtime_services()
    if not services.scheduler:
        raise HTTPException(status_code=404, detail="scheduler service not enabled")
    return await services.scheduler.run_task_now(task_id)


@router.get("/scheduler/logs")
async def scheduler_logs(limit: int = 200):
    services = get_runtime_services()
    if not services.scheduler:
        raise HTTPException(status_code=404, detail="scheduler service not enabled")
    return {"logs": services.scheduler.read_logs(limit=limit)}


@router.get("/heartbeat/status")
async def heartbeat_status():
    services = get_runtime_services()
    if not services.heartbeat:
        return {"enabled": False}
    return {"enabled": True, **services.heartbeat.status()}


@router.get("/clawhub/status")
async def clawhub_status():
    services = get_runtime_services()
    if not services.clawhub:
        return {"enabled": False}
    return {"enabled": True, **services.clawhub.status()}


@router.post("/clawhub/sync")
async def clawhub_sync():
    services = get_runtime_services()
    if not services.clawhub:
        raise HTTPException(status_code=404, detail="clawhub service not enabled")
    return await services.clawhub.sync_once()


@router.get("/clawhub/skills")
async def clawhub_skills():
    services = get_runtime_services()
    if not services.clawhub:
        raise HTTPException(status_code=404, detail="clawhub service not enabled")
    return {"skills": services.clawhub.list_skills()}


@router.post("/clawhub/skills/{name}/invoke")
async def clawhub_invoke(name: str, req: SkillInvokeRequest):
    services = get_runtime_services()
    if not services.clawhub:
        raise HTTPException(status_code=404, detail="clawhub service not enabled")
    try:
        result = await services.clawhub.invoke_skill(name, req.payload, req.context)
        return {"ok": True, "result": result}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/clawhub/skills/{name}/load")
async def clawhub_load(name: str, file_path: str, version: str = "local", entrypoint: str = "run"):
    services = get_runtime_services()
    if not services.clawhub:
        raise HTTPException(status_code=404, detail="clawhub service not enabled")
    return services.clawhub.load_skill(name, Path(file_path), version=version, entrypoint=entrypoint)


@router.post("/clawhub/skills/{name}/unload")
async def clawhub_unload(name: str):
    services = get_runtime_services()
    if not services.clawhub:
        raise HTTPException(status_code=404, detail="clawhub service not enabled")
    return {"ok": services.clawhub.unload_skill(name)}


@router.get("/openclaw/status")
async def openclaw_status():
    services = get_runtime_services()
    if not services.openclaw:
        return {"enabled": False}
    return {"enabled": True, **services.openclaw.status()}


@router.get("/openclaw/health")
async def openclaw_health():
    services = get_runtime_services()
    if not services.openclaw:
        raise HTTPException(status_code=404, detail="openclaw service not enabled")
    return await services.openclaw.health()


@router.post("/openclaw/invoke")
async def openclaw_invoke(req: OpenClawInvokeRequest):
    services = get_runtime_services()
    if not services.openclaw:
        raise HTTPException(status_code=404, detail="openclaw service not enabled")
    return await services.openclaw.invoke_tool(
        tool=req.tool,
        args=req.args,
        action=req.action,
        session_key=req.session_key,
    )
