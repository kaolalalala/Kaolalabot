from pathlib import Path

import pytest

from kaolalabot.agent.tools.playwright import PlaywrightTool


def test_playwright_tool_requires_input():
    tool = PlaywrightTool(workspace=Path("."))
    errors = tool.validate_params({})
    assert errors


@pytest.mark.asyncio
async def test_playwright_tool_openclaw_backend_dispatch(monkeypatch):
    tool = PlaywrightTool(workspace=Path("."), backend="openclaw")

    async def _fake(payload):
        assert payload["url"] == "https://example.com"
        return "ok-openclaw"

    monkeypatch.setattr(tool, "_run_openclaw", _fake)
    out = await tool.execute(url="https://example.com")
    assert out == "ok-openclaw"


@pytest.mark.asyncio
async def test_playwright_tool_native_backend_dispatch(monkeypatch):
    tool = PlaywrightTool(workspace=Path("."), backend="native")

    async def _fake(payload):
        assert payload["headless"] is False
        return "ok-native"

    monkeypatch.setattr(tool, "_run_native", _fake)
    out = await tool.execute(url="https://example.com", headless=False)
    assert out == "ok-native"
