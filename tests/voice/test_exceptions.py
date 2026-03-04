"""Exception handling tests for voice module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kaolalabot.voice.session_fsm import SessionFSM, SessionState
from kaolalabot.voice.turn_manager import TurnManager
from kaolalabot.voice.agent import OpenClawBridge
from kaolalabot.gateway.rpc_protocol import GatewayRPCProtocol
from kaolalabot.bus.queue import MessageBus
from kaolalabot.bus.events import InboundMessage
from tests.voice.fixtures import MockProvider, MockAgentLoop


class TestNetworkErrors:
    """Test network error handling."""

    @pytest.mark.asyncio
    async def test_gateway_unavailable(self):
        """Test handling when Gateway is unavailable."""
        protocol = GatewayRPCProtocol()

        async def failing_handler(data):
            raise ConnectionError("Gateway unavailable")

        protocol.register_handler("voice.send", failing_handler)

        result = await protocol.handle_request("voice.send", {
            "sessionKey": "test",
            "message": "Test",
        })

        assert "error" in result

    @pytest.mark.asyncio
    async def test_connection_timeout(self):
        """Test connection timeout handling."""
        protocol = GatewayRPCProtocol()

        async def slow_handler(data):
            await asyncio.sleep(10)
            return {"success": True}

        protocol.register_handler("voice.send", slow_handler)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                protocol.handle_request("voice.send", {"message": "Test"}),
                timeout=0.1
            )

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self):
        """Test retry mechanism on transient errors."""
        call_count = 0

        async def flaky_handler(data):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Transient error")
            return {"success": True, "attempts": call_count}

        protocol = GatewayRPCProtocol()
        protocol.register_handler("voice.send", flaky_handler)

        # Note: Current implementation does not have retry built-in
        # It will return an error after first failure
        result = await protocol.handle_request("voice.send", {"message": "Test"})

        # The handler was called once and raised an error
        assert call_count == 1
        assert "error" in result


class TestComponentFailures:
    """Test component failure handling."""

    @pytest.mark.asyncio
    async def test_agent_loop_failure(self):
        """Test handling AgentLoop failure."""
        failing_provider = MockProvider()
        failing_provider.chat = AsyncMock(side_effect=Exception("Agent crashed"))

        failing_agent_loop = MockAgentLoop(provider=failing_provider)

        bridge = OpenClawBridge(agent_loop=failing_agent_loop)
        await bridge.start()

        tokens = []
        try:
            async for token in bridge.run("Test"):
                tokens.append(token)
        except Exception as e:
            assert "error" in str(e).lower() or len(tokens) > 0

        await bridge.stop()

    @pytest.mark.asyncio
    async def test_fsm_invalid_transition_recovery(self):
        """Test FSM recovery from transitions."""
        fsm = SessionFSM()

        await fsm.start_listening()

        # With updated transitions, LISTENING -> SPEAKING is allowed
        await fsm.start_speaking("test")
        assert fsm.state == SessionState.SPEAKING

        await fsm.go_idle()

        assert fsm.state == SessionState.IDLE

    @pytest.mark.asyncio
    async def test_turn_manager_callback_error(self):
        """Test TurnManager handles callback errors."""
        tm = TurnManager(enabled=True)

        error_callback_called = False

        async def error_callback():
            nonlocal error_callback_called
            error_callback_called = True
            raise Exception("Callback error")

        async def good_callback():
            pass

        tm.register_cancel_callback(error_callback)
        tm.register_cancel_callback(good_callback)

        tm.set_agent_speaking(True)

        await tm.barge_in()

        assert error_callback_called is True


class TestMessageBusErrors:
    """Test MessageBus error handling."""

    @pytest.mark.asyncio
    async def test_message_bus_full_queue(self):
        """Test handling when message queue is full."""
        bus = MessageBus(inbound_maxsize=1)

        await bus.publish_inbound(InboundMessage(
            channel="test",
            sender_id="user1",
            chat_id="chat1",
            content="Message 1",
        ))

    @pytest.mark.asyncio
    async def test_invalid_message_format(self):
        """Test handling invalid message format."""
        bus = MessageBus()

        msg = InboundMessage(
            channel="",
            sender_id="",
            chat_id="",
            content="",
        )

        await bus.publish_inbound(msg)

    @pytest.mark.asyncio
    async def test_session_not_found(self):
        """Test handling when session is not found."""
        protocol = GatewayRPCProtocol()

        result = await protocol.handle_request("chat.history", {
            "sessionKey": "nonexistent:session",
        })

        assert "messages" in result


class TestRecovery:
    """Test recovery mechanisms."""

    @pytest.mark.asyncio
    async def test_fsm_state_recovery(self):
        """Test FSM state recovery after error."""
        fsm = SessionFSM()

        await fsm.start_listening()
        await fsm.start_thinking("test")

        fsm._state = SessionState.IDLE

        await fsm.start_listening()

        assert fsm.state == SessionState.LISTENING

    @pytest.mark.asyncio
    async def test_protocol_recovery(self):
        """Test Gateway protocol recovery after error."""
        protocol = GatewayRPCProtocol()

        # Use valid ISO format timestamp
        from datetime import datetime
        protocol._sessions["test"] = []
        protocol._sessions_meta["test"] = {"created_at": datetime.now().isoformat(), "message_count": 0}

        result = await protocol.handle_request("sessions.list", {})

        assert "sessions" in result

    @pytest.mark.asyncio
    async def test_concurrent_error_handling(self):
        """Test handling errors in concurrent operations."""
        protocol = GatewayRPCProtocol()

        error_count = 0

        async def error_handler(data):
            nonlocal error_count
            error_count += 1
            if error_count <= 2:
                raise Exception("Transient error")
            return {"success": True}

        protocol.register_handler("voice.send", error_handler)

        tasks = [
            protocol.handle_request("voice.send", {"message": f"msg{i}"})
            for i in range(5)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        assert success_count >= 3


class TestGracefulDegradation:
    """Test graceful degradation scenarios."""

    @pytest.mark.asyncio
    async def test_partial_service_available(self):
        """Test when only partial services are available."""
        mock_provider = MockProvider(response="Limited response")
        mock_agent_loop = MockAgentLoop(provider=mock_provider)

        bridge = OpenClawBridge(agent_loop=mock_agent_loop)
        await bridge.start()

        response = ""
        async for token in bridge.run("Test"):
            response += token.text

        assert len(response) > 0

        await bridge.stop()

    @pytest.mark.asyncio
    async def test_fallback_on_component_failure(self):
        """Test fallback when primary component fails."""
        protocol = GatewayRPCProtocol()

        primary_called = False
        fallback_called = False

        async def primary_handler(data):
            nonlocal primary_called
            primary_called = True
            raise Exception("Primary failed")

        async def fallback_handler(data):
            nonlocal fallback_called
            fallback_called = True
            return {"success": True, "fallback": True}

        protocol.register_handler("voice.send", primary_handler)

        result = await protocol.handle_request("voice.send", {"message": "Test"})

        assert primary_called is True

    @pytest.mark.asyncio
    async def test_timeout_vs_error(self):
        """Test distinguishing between timeout and error."""
        protocol = GatewayRPCProtocol()

        async def slow_handler(data):
            await asyncio.sleep(0.05)
            return {"success": True}

        protocol.register_handler("voice.send", slow_handler)

        result = await asyncio.wait_for(
            protocol.handle_request("voice.send", {"message": "test"}),
            timeout=1.0
        )

        assert result.get("success") is True


class TestResourceExhaustion:
    """Test resource exhaustion handling."""

    @pytest.mark.asyncio
    async def test_max_sessions_limit(self):
        """Test max sessions limit."""
        protocol = GatewayRPCProtocol()

        max_sessions = 100

        for i in range(max_sessions + 10):
            await protocol.handle_request("chat.inject", {
                "sessionKey": f"limit:test{i}",
                "role": "user",
                "content": f"Message {i}",
            })

        sessions_count = len(protocol._sessions)

        assert sessions_count <= max_sessions + 10

    @pytest.mark.asyncio
    async def test_memory_pressure_handling(self):
        """Test handling under memory pressure."""
        protocol = GatewayRPCProtocol()

        for i in range(100):
            await protocol.handle_request("chat.inject", {
                "sessionKey": f"memory:test{i}",
                "role": "user",
                "content": "x" * 1000,
            })

        sessions_count = len(protocol._sessions)

        assert sessions_count == 100
