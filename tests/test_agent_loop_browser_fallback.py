from pathlib import Path
import json

import pytest

from kaolalabot.agent.loop import AgentLoop
from kaolalabot.bus.events import InboundMessage
from kaolalabot.bus.queue import MessageBus
from kaolalabot.config.schema import Config
from kaolalabot.providers.base import LLMProvider, LLMResponse


class DummyProvider(LLMProvider):
    async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7, reasoning_effort=None):
        return LLMResponse(content="ok")

    def get_default_model(self) -> str:
        return "dummy-model"


@pytest.mark.asyncio
async def test_browser_workflow_fallbacks_to_playwright_when_openclaw_fails(monkeypatch):
    bus = MessageBus()
    cfg = Config()
    cfg.tools.kaola_browser.enabled = False
    cfg.tools.openclaw_browser.enabled = True
    loop = AgentLoop(bus=bus, provider=DummyProvider(), workspace=Path("."), channels_config=cfg.channels, tools_config=cfg.tools)

    calls = []

    async def _fake_execute(name, params):
        calls.append(name)
        if name == "openclaw_browser":
            return "Error: OpenClaw unavailable"
        if name == "playwright":
            return '{"ok":true,"steps":[{"action":"navigate","ok":true}]}'
        return "ok"

    monkeypatch.setattr(loop.tools, "execute", _fake_execute)
    monkeypatch.setattr(loop.tools, "has", lambda name: name == "openclaw_browser")

    msg = InboundMessage(
        channel="feishu",
        sender_id="u1",
        chat_id="ou_1",
        content="在谷歌浏览器搜索github网页，并且在该网页里搜索agent reach项目",
    )
    resp = await loop._process_message(msg)
    assert resp is not None
    assert "openclaw_browser" in calls
    assert "playwright" in calls


@pytest.mark.asyncio
async def test_browser_workflow_prefers_kaola_browser_when_available(monkeypatch):
    bus = MessageBus()
    cfg = Config()
    cfg.tools.kaola_browser.enabled = True
    cfg.tools.openclaw_browser.enabled = True
    loop = AgentLoop(bus=bus, provider=DummyProvider(), workspace=Path("."), channels_config=cfg.channels, tools_config=cfg.tools)

    calls = []

    async def _fake_execute(name, params):
        calls.append(name)
        if name == "kaola_browser":
            action = params.get("action")
            if action == "snapshot":
                return "textbox [ref=e12] Search or jump to..."
            return '{"ok":true}'
        if name == "openclaw_browser":
            return "Error: should not be called"
        if name == "playwright":
            return "Error: should not be called"
        return "ok"

    monkeypatch.setattr(loop.tools, "execute", _fake_execute)
    monkeypatch.setattr(loop.tools, "has", lambda name: name in ("kaola_browser", "openclaw_browser"))

    result = await loop._run_browser_automation_plan(
        type(
            "Plan",
            (),
            {
                "tool_args": {
                    "workflow": {
                        "outer_query": "github",
                        "inner_query": "agent reach",
                        "target_url": "https://github.com",
                    }
                },
                "tool_name": "playwright",
            },
        )()
    )
    assert "kaola_browser" in calls
    assert "openclaw_browser" not in calls
    assert "playwright" not in calls
    assert '"ok": true' in result.lower()


@pytest.mark.asyncio
async def test_browser_workflow_uses_snapshot_ref_and_act(monkeypatch):
    bus = MessageBus()
    cfg = Config()
    cfg.tools.kaola_browser.enabled = False
    cfg.tools.openclaw_browser.enabled = True
    loop = AgentLoop(bus=bus, provider=DummyProvider(), workspace=Path("."), channels_config=cfg.channels, tools_config=cfg.tools)

    calls = []

    async def _fake_execute(name, params):
        calls.append((name, params))
        if name == "openclaw_browser":
            action = params.get("action")
            if action == "snapshot":
                return "textbox [ref=e12] Search or jump to..."
            return '{"ok":true}'
        return "ok"

    monkeypatch.setattr(loop.tools, "execute", _fake_execute)
    monkeypatch.setattr(loop.tools, "has", lambda name: name == "openclaw_browser")

    msg = InboundMessage(
        channel="feishu",
        sender_id="u1",
        chat_id="ou_1",
        content="在谷歌浏览器搜索github网页，并且在该网页里搜索agent reach项目",
    )
    resp = await loop._process_message(msg)
    assert resp is not None
    browser_calls = [p for n, p in calls if n == "openclaw_browser"]
    assert any(c.get("action") == "act" for c in browser_calls)


@pytest.mark.asyncio
async def test_browser_workflow_falls_back_to_navigate_when_act_fails(monkeypatch):
    bus = MessageBus()
    cfg = Config()
    cfg.tools.kaola_browser.enabled = False
    cfg.tools.openclaw_browser.enabled = True
    loop = AgentLoop(bus=bus, provider=DummyProvider(), workspace=Path("."), channels_config=cfg.channels, tools_config=cfg.tools)

    calls = []

    async def _fake_execute(name, params):
        calls.append((name, params))
        if name == "openclaw_browser":
            action = params.get("action")
            if action == "snapshot":
                return "textbox [ref=e12] Search or jump to..."
            if action == "act":
                return "Error: click failed"
            return '{"ok":true}'
        if name == "playwright":
            return '{"ok":true}'
        return "ok"

    monkeypatch.setattr(loop.tools, "execute", _fake_execute)
    monkeypatch.setattr(loop.tools, "has", lambda name: name == "openclaw_browser")

    result = await loop._run_openclaw_browser_workflow(
        {"outer_query": "github", "inner_query": "agent reach", "target_url": "https://github.com"}
    )
    parsed = json.loads(result)
    assert parsed["ok"] is True
    browser_calls = [p for n, p in calls if n == "openclaw_browser"]
    assert any(c.get("action") == "act" for c in browser_calls)
    assert any(c.get("action") == "navigate" for c in browser_calls)


def test_extract_ref_from_json_snapshot_prefers_search_box():
    snapshot = '{"snapshot":"link [ref=e1] Sign in\\ntextbox [ref=e12] Search or jump to..."}'
    ref = AgentLoop._extract_ref_from_snapshot(snapshot, preferred_terms=["search", "jump"])
    assert ref == "e12"
