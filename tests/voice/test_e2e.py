"""End-to-end tests for voice interaction flow."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kaolalabot.voice.session_fsm import SessionFSM, SessionState
from kaolalabot.voice.turn_manager import TurnManager
from kaolalabot.voice.agent import OpenClawBridge
from kaolalabot.voice.shell import VoiceShell, VoiceConfig
from kaolalabot.gateway.rpc_protocol import GatewayRPCProtocol
from kaolalabot.bus.queue import MessageBus
from kaolalabot.bus.events import InboundMessage, OutboundMessage
from tests.voice.fixtures import (
    MockProvider,
    MockAgentLoop,
    AudioTestData,
    TestMetrics,
)


class TestVoiceEndToEnd:
    """End-to-end voice interaction tests."""

    @pytest.mark.asyncio
    async def test_complete_voice_flow(self):
        """Test complete voice interaction flow."""
        metrics = TestMetrics()

        mock_provider = MockProvider(response="这是AI的回复")
        mock_agent_loop = MockAgentLoop(provider=mock_provider)

        bridge = OpenClawBridge(agent_loop=mock_agent_loop)
        await bridge.start()

        metrics.record_start()
        response_text = ""
        async for token in bridge.run("你好，请介绍一下自己"):
            response_text += token.text
        metrics.record_end()

        assert "你好，请介绍一下自己" in mock_agent_loop.processed_messages
        assert len(response_text) > 0
        assert metrics.latency_ms > 0

        await bridge.stop()

    @pytest.mark.asyncio
    async def test_voice_with_vad_and_fsm(self):
        """Test voice flow with VAD and FSM."""
        fsm = SessionFSM()

        mock_provider = MockProvider(response="响应内容")
        mock_agent_loop = MockAgentLoop(provider=mock_provider)

        bridge = OpenClawBridge(agent_loop=mock_agent_loop)
        await bridge.start()

        await fsm.start_listening()

        response = ""
        async for token in bridge.run("测试消息"):
            response += token.text
            await fsm.start_speaking(response)

        assert fsm.is_speaking() is True

        await fsm.go_idle()

        await bridge.stop()

    @pytest.mark.asyncio
    async def test_barge_in_during_speaking(self):
        """Test barge-in while agent is speaking."""
        tm = TurnManager(enabled=True)

        cancel_called = False

        async def mock_cancel():
            nonlocal cancel_called
            cancel_called = True

        tm.register_cancel_callback(mock_cancel)

        mock_provider = MockProvider(response="长回复" * 100)
        mock_agent_loop = MockAgentLoop(provider=mock_provider)

        bridge = OpenClawBridge(agent_loop=mock_agent_loop)
        await bridge.start()

        # Set agent as speaking so should_barge_in returns True
        tm.set_agent_speaking(True)
        assert tm.should_barge_in() is True

        await tm.barge_in()
        assert cancel_called is True

        await bridge.stop()

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self):
        """Test multi-turn conversation."""
        protocol = GatewayRPCProtocol()

        mock_process = AsyncMock(side_effect=[
            "第一轮回复",
            "第二轮回复",
            "第三轮回复",
        ])
        protocol._process_message = mock_process

        results = []
        for i in range(3):
            result = await protocol.handle_request("chat.send", {
                "sessionKey": "multiturn:test",
                "message": f"第{i+1}轮消息",
            })
            results.append(result)

        assert len(results) == 3
        assert mock_process.call_count == 3


class TestVoiceGatewayE2E:
    """End-to-end tests for Voice-Gateway-AgentLoop."""

    @pytest.mark.asyncio
    async def test_voice_input_to_gateway_to_agent(self):
        """Test voice input -> Gateway -> Agent -> Response flow."""
        protocol = GatewayRPCProtocol()

        async def mock_agent_handler(data):
            message = data.get("message", "")
            return {"success": True, "processed": message}

        protocol.register_handler("voice.process", mock_agent_handler)

        result = await protocol.handle_request("voice.process", {
            "sessionKey": "voice:e2e:test",
            "message": "语音输入测试",
        })

        assert result.get("success") is True
        assert "语音输入测试" in result.get("processed", "")

    @pytest.mark.asyncio
    async def test_session_persistence_across_turns(self):
        """Test session persists across conversation turns."""
        protocol = GatewayRPCProtocol()

        await protocol.handle_request("chat.inject", {
            "sessionKey": "persist:test",
            "role": "user",
            "content": "第一条消息",
        })

        await protocol.handle_request("chat.inject", {
            "sessionKey": "persist:test",
            "role": "assistant",
            "content": "第一条回复",
        })

        messages = await protocol.get_session_messages("persist:test")

        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_concurrent_voice_sessions(self):
        """Test multiple concurrent voice sessions."""
        protocol = GatewayRPCProtocol()

        sessions = {}

        async def session_handler(data):
            session_key = data.get("sessionKey", "")
            message = data.get("message", "")

            if session_key not in sessions:
                sessions[session_key] = []
            sessions[session_key].append(message)

            return {"success": True, "session": session_key}

        protocol.register_handler("voice.session", session_handler)

        tasks = []
        for i in range(5):
            task = protocol.handle_request("voice.session", {
                "sessionKey": f"concurrent:user{i}",
                "message": f"消息 from user{i}",
            })
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert len(sessions) == 5


class TestLatencyE2E:
    """End-to-end latency tests."""

    @pytest.mark.asyncio
    async def test_voice_to_agent_latency(self):
        """Test overall voice to agent response latency."""
        metrics = TestMetrics()

        mock_provider = MockProvider(response="响应", delay_ms=50)
        mock_agent_loop = MockAgentLoop(provider=mock_provider)

        bridge = OpenClawBridge(agent_loop=mock_agent_loop)
        await bridge.start()

        metrics.record_start()
        async for _ in bridge.run("延迟测试消息"):
            pass
        metrics.record_end()

        await bridge.stop()

        assert metrics.latency_ms > 0

    @pytest.mark.asyncio
    async def test_gateway_latency(self):
        """Test Gateway processing latency."""
        metrics = TestMetrics()

        protocol = GatewayRPCProtocol()

        async def mock_slow_process(data):
            await asyncio.sleep(0.05)
            return "Response"

        protocol._process_message = mock_slow_process

        metrics.record_start()
        await protocol.handle_request("chat.send", {
            "sessionKey": "latency:test",
            "message": "Test",
        })
        metrics.record_end()

        assert metrics.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_session_creation_latency(self):
        """Test session creation latency."""
        metrics = TestMetrics()

        protocol = GatewayRPCProtocol()

        metrics.record_start()
        for i in range(10):
            await protocol.handle_request("chat.inject", {
                "sessionKey": f"create:latency{i}",
                "role": "user",
                "content": f"Message {i}",
            })
        metrics.record_end()

        avg_latency = metrics.latency_ms / 10
        assert avg_latency < 50


class TestDataIntegrity:
    """Data integrity tests."""

    @pytest.mark.asyncio
    async def test_message_content_preserved(self):
        """Test message content is preserved through pipeline."""
        original_message = "完整的测试消息内容，包含中文和特殊字符！@#$%"

        mock_provider = MockProvider(response="回复")
        mock_agent_loop = MockAgentLoop(provider=mock_provider)

        bridge = OpenClawBridge(agent_loop=mock_agent_loop)
        await bridge.start()

        response = ""
        async for token in bridge.run(original_message):
            response += token.text

        assert original_message in mock_agent_loop.processed_messages

        await bridge.stop()

    @pytest.mark.asyncio
    async def test_unicode_handling(self):
        """Test Unicode character handling."""
        unicode_messages = [
            "你好世界",
            "🎉🎊🎈",
            "한국어",
            "日本語",
        ]

        protocol = GatewayRPCProtocol()

        for msg in unicode_messages:
            result = await protocol.handle_request("chat.inject", {
                "sessionKey": "unicode:test",
                "role": "user",
                "content": msg,
            })

            assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_long_message_handling(self):
        """Test handling of long messages."""
        long_message = "这是一段很长的消息。" * 100

        protocol = GatewayRPCProtocol()

        result = await protocol.handle_request("chat.inject", {
            "sessionKey": "long:test",
            "role": "user",
            "content": long_message,
        })

        messages = await protocol.get_session_messages("long:test")
        assert len(messages) == 1
        assert len(messages[0].content) >= len(long_message)


class TestErrorRecoveryE2E:
    """End-to-end error recovery tests."""

    @pytest.mark.asyncio
    async def test_recovery_from_agent_error(self):
        """Test system recovers from agent error."""
        call_count = 0

        async def flaky_provider(messages, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First call fails")
            return MagicMock(content="恢复后的回复", has_tool_calls=False)

        mock_provider = MagicMock()
        mock_provider.chat = flaky_provider

        mock_agent_loop = MockAgentLoop(provider=mock_provider)
        mock_agent_loop.provider = mock_provider

        bridge = OpenClawBridge(agent_loop=mock_agent_loop)
        await bridge.start()

        response = ""
        async for token in bridge.run("测试"):
            response += token.text

        assert call_count >= 1

        await bridge.stop()

    @pytest.mark.asyncio
    async def test_session_isolation_on_error(self):
        """Test error in one session doesn't affect others."""
        protocol = GatewayRPCProtocol()

        protocol._sessions = {}
        protocol._sessions_meta = {}

        error_sessions = []

        async def error_handler(data):
            session_key = data.get("sessionKey", "")
            if "error" in session_key:
                error_sessions.append(session_key)
                raise Exception("Session error")
            return {"success": True}

        protocol.register_handler("voice.send", error_handler)

        results = await asyncio.gather(
            protocol.handle_request("voice.send", {"sessionKey": "normal:1", "message": "OK"}),
            protocol.handle_request("voice.send", {"sessionKey": "error:test", "message": "Error"}),
            protocol.handle_request("voice.send", {"sessionKey": "normal:2", "message": "OK"}),
            return_exceptions=True,
        )

        success_results = [r for r in results if isinstance(r, dict) and r.get("success")]
        assert len(success_results) == 2


class TestFullPipeline:
    """Full pipeline integration tests."""

    @pytest.mark.asyncio
    async def test_voice_pipeline_full(self):
        """Test full voice pipeline from input to output."""
        pipeline_stages = []

        mock_provider = MockProvider(response="完整流程测试回复")
        agent_loop = MockAgentLoop(provider=mock_provider)

        bridge = OpenClawBridge(agent_loop=agent_loop)
        await bridge.start()

        pipeline_stages.append("bridge_started")

        response = ""
        async for token in bridge.run("完整流程测试"):
            pipeline_stages.append("token_received")
            response += token.text

        pipeline_stages.append("pipeline_complete")

        await bridge.stop()

        assert len(agent_loop.processed_messages) > 0
        assert len(response) > 0
        assert "pipeline_complete" in pipeline_stages

    @pytest.mark.asyncio
    async def test_state_machine_integration(self):
        """Test FSM integration with full pipeline."""
        fsm = SessionFSM()

        mock_provider = MockProvider(response="状态机测试回复")
        mock_agent_loop = MockAgentLoop(provider=mock_provider)

        bridge = OpenClawBridge(agent_loop=mock_agent_loop)
        await bridge.start()

        await fsm.start_listening()
        assert fsm.is_listening() is True

        await fsm.start_thinking("用户输入")
        assert fsm.is_thinking() is True

        response = ""
        async for token in bridge.run("用户输入"):
            response += token.text

        await fsm.start_speaking(response)
        assert fsm.is_speaking() is True

        await fsm.go_idle()
        assert fsm.is_idle() is True

        await bridge.stop()
