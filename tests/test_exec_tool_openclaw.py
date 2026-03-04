from pathlib import Path

import pytest

from kaolalabot.agent.tools.exec import ExecTool


@pytest.mark.asyncio
async def test_exec_openclaw_backend_dispatch(monkeypatch):
    tool = ExecTool(workspace=Path("."), timeout=10, backend="openclaw")

    async def _fake_run(command: str, timeout: int, cwd: str) -> str:
        assert command == "echo hi"
        assert timeout == 10
        assert cwd
        return "ok-from-openclaw"

    monkeypatch.setattr(tool, "_run_command_openclaw", _fake_run)
    output = await tool.execute("echo hi")
    assert output == "ok-from-openclaw"


@pytest.mark.asyncio
async def test_exec_openclaw_backend_respects_deny_policy():
    tool = ExecTool(
        workspace=Path("."),
        timeout=10,
        backend="openclaw",
        deny_commands=["powershell"],
    )
    output = await tool.execute('start "" powershell')
    assert "not allowed" in output.lower()
