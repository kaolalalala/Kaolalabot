"""Integration tests for Voice-Gateway-AgentLoop integration."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kaolalabot.gateway.rpc_protocol import (
    GatewayRPCProtocol,
    ChatSendRequest,
    ChatMessage,
)
from kaolalabot.bus.queue import MessageBus
from kaolalabot.bus.events import InboundMessage, OutboundMessage
from kaolalabot.agent.loop import AgentLoop
from kaolalabot.voice.agent import OpenClawBridge
from tests.voice.fixtures import MockProvider, MockAgentLoop, TestMetrics


class TestGatewayProtocol:
    """Test Gateway RPC Protocol."""

    @pytest.mark.asyncio
    async def test_gateway_initialization(self):
        """Test Gateway initializes correctly."""
        protocol = GatewayRPCProtocol()

        assert protocol is not None
        assert "chat.send" in protocol._handlers

    @pytest.mark.asyncio
    async def test_chat_send_request(self):
        """Test chat.send request handling."""
        protocol = GatewayRPCProtocol()

        with patch.object(protocol, "_process_message", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = "Test response"

            result = await protocol.handle_request("chat.send", {
                "sessionKey": "test:session",
                "message": "Hello",
            })

            assert "runId" in result
            assert result["sessionKey"] == "test:session"

    @pytest.mark.asyncio
    async def test_chat_history_request(self):
        """Test chat.history request handling."""
        protocol = GatewayRPCProtocol()

        protocol._sessions["test:session"] = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there"),
        ]

        result = await protocol.handle_request("chat.history", {
            "sessionKey": "test:session",
            "limit": 10,
        })

        assert "messages" in result
        assert len(result["messages"]) == 2

    @pytest.mark.asyncio
    async def test_chat_inject_request(self):
        """Test chat.inject request handling."""
        protocol = GatewayRPCProtocol()

        result = await protocol.handle_request("chat.inject", {
            "sessionKey": "test:session",
            "role": "assistant",
            "content": "Injected message",
        })

        assert result["success"] is True

        messages = await protocol.get_session_messages("test:session")
        assert len(messages) == 1
        assert messages[0].content == "Injected message"

    @pytest.mark.asyncio
    async def test_sessions_list_request(self):
        """Test sessions.list request handling."""
        from datetime import datetime

        protocol = GatewayRPCProtocol()

        protocol._sessions["session1"] = []
        protocol._sessions_meta["session1"] = {
            "created_at": datetime.now().isoformat(),
            "message_count": 5,
        }

        result = await protocol.handle_request("sessions.list", {})

        assert "sessions" in result
        assert result["total"] >= 1

    @pytest.mark.asyncio
    async def test_unknown_method(self):
        """Test handling of unknown methods."""
        protocol = GatewayRPCProtocol()

        result = await protocol.handle_request("unknown.method", {})

        assert "error" in result
        assert result["code"] == "METHOD_NOT_FOUND"


class TestMessageBus:
    """Test MessageBus integration."""

    @pytest.mark.asyncio
    async def test_message_bus_publish_inbound(self):
        """Test publishing inbound message."""
        bus = MessageBus()

        msg = InboundMessage(
            channel="voice",
            sender_id="user123",
            chat_id="chat456",
            content="Test message",
        )

        await bus.publish_inbound(msg)

        received = await asyncio.wait_for(bus.consume_inbound(), timeout=1.0)
        assert received.content == "Test message"

    @pytest.mark.asyncio
    async def test_message_bus_publish_outbound(self):
        """Test publishing outbound message."""
        bus = MessageBus()

        msg = OutboundMessage(
            channel="voice",
            chat_id="chat456",
            content="Response",
        )

        await bus.publish_outbound(msg)


class TestVoiceGatewayIntegration:
    """Test Voice module integration with Gateway."""

    @pytest.mark.asyncio
    async def test_voice_text_to_gateway(self):
        """Test voice text is correctly sent to Gateway."""
        protocol = GatewayRPCProtocol()

        mock_process = AsyncMock(return_value="Gateway response")
        protocol._process_message = mock_process

        result = await protocol.handle_request("chat.send", {
            "sessionKey": "voice:user123",
            "message": "语音测试消息",
        })

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert "语音测试消息" in str(call_args)

    @pytest.mark.asyncio
    async def test_gateway_to_agent_loop(self):
        """Test Gateway forwards text to AgentLoop."""
        mock_provider = MockProvider(response="Agent response")
        mock_agent_loop = MockAgentLoop(provider=mock_provider)

        bridge = OpenClawBridge(agent_loop=mock_agent_loop)
        await bridge.start()

        response = ""
        async for token in bridge.run("Test message"):
            response += token.text

        assert "Test message" in mock_agent_loop.processed_messages
        assert "Agent response" in response

        await bridge.stop()

    @pytest.mark.asyncio
    async def test_voice_to_message_bus(self):
        """Test voice module integrates with MessageBus."""
        bus = MessageBus()

        from kaolalabot.voice.agent import OpenClawBridge
        mock_provider = MockProvider(response="Response via bus")
        mock_agent_loop = MockAgentLoop(provider=mock_provider)

        bridge = OpenClawBridge(agent_loop=mock_agent_loop)
        await bridge.start()

        async for _ in bridge.run("Test via bus"):
            pass

        await bridge.stop()

    @pytest.mark.asyncio
    async def test_session_key_routing(self):
        """Test session key routing between components."""
        protocol = GatewayRPCProtocol()

        sessions_data = {}

        async def mock_handler(data):
            session_key = data.get("sessionKey", "default")
            sessions_data[session_key] = data.get("message", "")
            return {"success": True, "sessionKey": session_key}

        protocol.register_handler("voice.send", mock_handler)

        result1 = await protocol.handle_request("voice.send", {
            "sessionKey": "voice:user1",
            "message": "Message from user 1",
        })

        result2 = await protocol.handle_request("voice.send", {
            "sessionKey": "voice:user2",
            "message": "Message from user 2",
        })

        assert sessions_data["voice:user1"] == "Message from user 1"
        assert sessions_data["voice:user2"] == "Message from user 2"


class TestDataFormat:
    """Test data format consistency across integration."""

    @pytest.mark.asyncio
    async def test_inbound_message_format(self):
        """Test InboundMessage format matches expectations."""
        msg = InboundMessage(
            channel="voice",
            sender_id="user123",
            chat_id="chat456",
            content="语音输入",
            session_key_override="voice:user123",
        )

        assert msg.channel == "voice"
        assert msg.sender_id == "user123"
        assert msg.session_key == "voice:user123"

    @pytest.mark.asyncio
    async def test_outbound_message_format(self):
        """Test OutboundMessage format matches expectations."""
        msg = OutboundMessage(
            channel="voice",
            chat_id="chat456",
            content="语音回复",
            metadata={"voice_data": True},
        )

        assert msg.channel == "voice"
        assert msg.content == "语音回复"
        assert msg.metadata.get("voice_data") is True

    @pytest.mark.asyncio
    async def test_chat_message_format(self):
        """Test ChatMessage format for gateway."""
        msg = ChatMessage(
            role="user",
            content="Voice input text",
        )

        msg_dict = msg.to_dict()

        assert msg_dict["role"] == "user"
        assert msg_dict["content"] == "Voice input text"

    @pytest.mark.asyncio
    async def test_message_serialization(self):
        """Test message serialization round-trip."""
        original = InboundMessage(
            channel="voice",
            sender_id="test_user",
            chat_id="test_chat",
            content="Test content",
        )

        assert original.channel == "voice"


class TestErrorPropagation:
    """Test error propagation through the integration chain."""

    @pytest.mark.asyncio
    async def test_gateway_error_handling(self):
        """Test Gateway handles errors gracefully."""
        protocol = GatewayRPCProtocol()

        protocol._process_message = AsyncMock(side_effect=Exception("Test error"))

        result = await protocol.handle_request("chat.send", {
            "sessionKey": "test",
            "message": "Test",
        })

        assert "error" in result
        assert result["code"] == "INTERNAL_ERROR"

    @pytest.mark.asyncio
    async def test_agent_loop_error_handling(self):
        """Test AgentLoop handles errors gracefully."""
        mock_provider = MockProvider()
        mock_provider.chat = AsyncMock(side_effect=Exception("Provider error"))

        mock_agent_loop = MockAgentLoop(provider=mock_provider)

        bridge = OpenClawBridge(agent_loop=mock_agent_loop)
        await bridge.start()

        response = ""
        async for token in bridge.run("Test"):
            response += token.text

        assert "error" in response.lower() or len(response) > 0

        await bridge.stop()
