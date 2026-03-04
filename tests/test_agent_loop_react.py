from pathlib import Path

import pytest

from kaolalabot.agent.loop import AgentLoop
from kaolalabot.bus.events import InboundMessage
from kaolalabot.bus.queue import MessageBus
from kaolalabot.config.schema import Config
from kaolalabot.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class ReactProvider(LLMProvider):
    def __init__(self):
        super().__init__()
        self.turn = 0

    async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7, reasoning_effort=None):
        self.turn += 1
        if self.turn == 1:
            return LLMResponse(
                content="Need tool support.",
                tool_calls=[ToolCallRequest(id="tc1", name="exec", arguments={"command": "echo hi"})],
            )
        return LLMResponse(content="Done after observation.")

    def get_default_model(self) -> str:
        return "dummy-model"


class NoToolProvider(LLMProvider):
    async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7, reasoning_effort=None):
        return LLMResponse(content="Direct answer without tools.")

    def get_default_model(self) -> str:
        return "dummy-model"


@pytest.mark.asyncio
async def test_react_mode_direct_response_without_tool():
    bus = MessageBus()
    config = Config()
    loop = AgentLoop(bus=bus, provider=NoToolProvider(), workspace=Path("."), channels_config=config.channels)

    msg = InboundMessage(channel="cli", sender_id="u1", chat_id="c1", content="just answer directly")
    resp = await loop._process_message(msg)
    assert resp is not None
    assert "direct answer" in resp.content.lower()


@pytest.mark.asyncio
async def test_react_mode_action_observation_closed_loop(monkeypatch):
    bus = MessageBus()
    config = Config()
    loop = AgentLoop(bus=bus, provider=ReactProvider(), workspace=Path("."), channels_config=config.channels)

    async def _fake_execute(name, params):
        assert name == "exec"
        return "Application launch command executed."

    monkeypatch.setattr(loop.tools, "execute", _fake_execute)

    msg = InboundMessage(channel="cli", sender_id="u1", chat_id="c1", content="open tool flow")
    resp = await loop._process_message(msg)
    assert resp is not None
    assert "observation" in "".join([m.get("content", "") for m in loop.sessions.get_or_create("cli:c1").messages]).lower()
    assert "done" in resp.content.lower()
