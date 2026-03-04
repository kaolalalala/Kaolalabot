from pathlib import Path

import pytest

from kaolalabot.agent.loop import AgentLoop
from kaolalabot.bus.events import InboundMessage
from kaolalabot.bus.queue import MessageBus
from kaolalabot.config.schema import Config
from kaolalabot.providers.base import LLMProvider, LLMResponse


class DummyProvider(LLMProvider):
    async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7, reasoning_effort=None):
        return LLMResponse(content='ok')

    def get_default_model(self) -> str:
        return 'dummy-model'


@pytest.mark.asyncio
async def test_help_command_no_deep_entries():
    bus = MessageBus()
    config = Config()
    loop = AgentLoop(bus=bus, provider=DummyProvider(), workspace=Path('.'), channels_config=config.channels)

    msg = InboundMessage(channel='cli', sender_id='u1', chat_id='c1', content='/help')
    resp = await loop._process_message(msg)

    assert resp is not None
    assert '/help' in resp.content
    assert '/deep' not in resp.content


@pytest.mark.asyncio
async def test_feishu_native_command_router_triggers_exec(monkeypatch):
    bus = MessageBus()
    config = Config()
    loop = AgentLoop(bus=bus, provider=DummyProvider(), workspace=Path('.'), channels_config=config.channels)

    calls = {}

    async def _fake_execute(name, params):
        calls["name"] = name
        calls["params"] = params
        return "Application launch command executed."

    monkeypatch.setattr(loop.tools, "execute", _fake_execute)

    msg = InboundMessage(channel='feishu', sender_id='u1', chat_id='ou_1', content='start powershell')
    resp = await loop._process_message(msg)

    assert resp is not None
    assert calls.get("name") == "exec"
    assert "powershell" in calls.get("params", {}).get("command", "").lower()
    assert "Executed:" in resp.content


@pytest.mark.asyncio
async def test_feishu_browser_workflow_triggers_playwright(monkeypatch):
    bus = MessageBus()
    config = Config()
    loop = AgentLoop(bus=bus, provider=DummyProvider(), workspace=Path('.'), channels_config=config.channels)

    calls = {}

    async def _fake_execute(name, params):
        calls["name"] = name
        calls["params"] = params
        return '{"ok":true,"steps":[{"action":"navigate","ok":true}]}'

    monkeypatch.setattr(loop.tools, "execute", _fake_execute)

    msg = InboundMessage(
        channel='feishu',
        sender_id='u1',
        chat_id='ou_1',
        content='在谷歌浏览器搜索github网页，并且在该网页里搜索agent reach项目',
    )
    resp = await loop._process_message(msg)

    assert resp is not None
    assert calls.get("name") == "playwright"
    assert "completed" in resp.content.lower()


@pytest.mark.asyncio
async def test_feishu_browser_workflow_prefers_openclaw_browser(monkeypatch):
    bus = MessageBus()
    config = Config()
    config.tools.openclaw_browser.enabled = True
    loop = AgentLoop(bus=bus, provider=DummyProvider(), workspace=Path('.'), channels_config=config.channels, tools_config=config.tools)

    calls = []

    async def _fake_execute(name, params):
        calls.append((name, params))
        if name == "openclaw_browser":
            return '{"ok":true}'
        if name == "playwright":
            return '{"ok":true}'
        if name == "exec":
            return "Application launch command executed."
        return "ok"

    monkeypatch.setattr(loop.tools, "execute", _fake_execute)
    monkeypatch.setattr(loop.tools, "has", lambda name: name == "openclaw_browser")

    msg = InboundMessage(
        channel='feishu',
        sender_id='u1',
        chat_id='ou_1',
        content='在谷歌浏览器搜索github网页，并且在该网页里搜索agent reach项目',
    )
    resp = await loop._process_message(msg)
    assert resp is not None
    assert any(name == "openclaw_browser" for name, _ in calls)
