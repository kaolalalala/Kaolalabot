"""Performance tests for voice module - latency and stability."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kaolalabot.voice.session_fsm import SessionFSM, SessionState
from kaolalabot.voice.turn_manager import TurnManager
from kaolalabot.voice.agent import OpenClawBridge
from kaolalabot.gateway.rpc_protocol import GatewayRPCProtocol
from tests.voice.fixtures import MockProvider, MockAgentLoop, TestMetrics


class TestPerformance:
    """Performance tests for voice module."""

    @pytest.mark.asyncio
    async def test_fsm_state_transition_latency(self):
        """Test FSM state transition latency."""
        metrics = TestMetrics()
        fsm = SessionFSM()

        metrics.record_start()
        await fsm.start_listening()
        await fsm.start_thinking("test")
        await fsm.start_speaking("response")
        await fsm.go_idle()
        metrics.record_end()

        assert metrics.latency_ms < 100, f"FSM transition too slow: {metrics.latency_ms}ms"

    @pytest.mark.asyncio
    async def test_turn_manager_barge_in_latency(self):
        """Test TurnManager barge-in response time."""
        metrics = TestMetrics()
        tm = TurnManager(enabled=True)

        cancel_count = 0

        async def mock_cancel():
            nonlocal cancel_count
            cancel_count += 1
            await asyncio.sleep(0.001)

        tm.register_cancel_callback(mock_cancel)
        tm.set_agent_speaking(True)

        metrics.record_start()
        await tm.barge_in()
        metrics.record_end()

        assert cancel_count == 1
        assert metrics.latency_ms < 50, f"Barge-in too slow: {metrics.latency_ms}ms"

    @pytest.mark.asyncio
    async def test_gateway_request_response_latency(self):
        """Test Gateway request-response latency."""
        metrics = TestMetrics()
        protocol = GatewayRPCProtocol()

        mock_process = AsyncMock(return_value="Fast response")
        protocol._process_message = mock_process

        metrics.record_start()
        result = await protocol.handle_request("chat.send", {
            "sessionKey": "perf:test",
            "message": "Performance test",
        })
        metrics.record_end()

        assert "runId" in result
        assert metrics.latency_ms < 1000, f"Gateway too slow: {metrics.latency_ms}ms"

    @pytest.mark.asyncio
    async def test_concurrent_session_handling(self):
        """Test handling multiple concurrent sessions."""
        protocol = GatewayRPCProtocol()

        sessions_count = 10

        async def mock_handler(data):
            await asyncio.sleep(0.01)
            return {"success": True, "sessionKey": data.get("sessionKey")}

        protocol.register_handler("voice.send", mock_handler)

        tasks = [
            protocol.handle_request("voice.send", {
                "sessionKey": f"voice:user{i}",
                "message": f"Message {i}",
            })
            for i in range(sessions_count)
        ]

        start = time.perf_counter()
        results = await asyncio.gather(*tasks)
        elapsed = (time.perf_counter() - start) * 1000

        assert len(results) == sessions_count
        assert elapsed < 2000, f"Concurrent sessions too slow: {elapsed}ms"

    @pytest.mark.asyncio
    async def test_message_throughput(self):
        """Test message processing throughput."""
        metrics = TestMetrics()
        protocol = GatewayRPCProtocol()

        mock_process = AsyncMock(return_value="Response")
        protocol._process_message = mock_process

        message_count = 50

        async def send_message(i):
            return await protocol.handle_request("chat.send", {
                "sessionKey": f"throughput:test{i}",
                "message": f"Message {i}",
            })

        metrics.record_start()
        results = await asyncio.gather(*[send_message(i) for i in range(message_count)])
        metrics.record_end()

        assert len(results) == message_count

        throughput = message_count / (metrics.latency_ms / 1000)
        assert throughput > 10, f"Throughput too low: {throughput:.2f} msg/s"


class TestStability:
    """Stability tests for voice module."""

    @pytest.mark.asyncio
    async def test_repeated_state_transitions(self):
        """Test FSM handles repeated state transitions."""
        fsm = SessionFSM()

        for _ in range(100):
            await fsm.start_listening()
            await fsm.start_thinking("test")
            await fsm.start_speaking("response")
            await fsm.go_idle()

        assert fsm.state == SessionState.IDLE

    @pytest.mark.asyncio
    async def test_rapid_barge_in(self):
        """Test rapid barge-in requests."""
        tm = TurnManager(enabled=True)
        cancel_count = 0

        async def mock_cancel():
            nonlocal cancel_count
            cancel_count += 1

        tm.register_cancel_callback(mock_cancel)
        tm.set_agent_speaking(True)

        for _ in range(20):
            await tm.barge_in()
            await asyncio.sleep(0.001)

        assert cancel_count == 20

    @pytest.mark.asyncio
    async def test_session_timeout(self):
        """Test session timeout handling."""
        fsm = SessionFSM(
            idle_timeout_seconds=0.1,
            thinking_timeout_seconds=0.1,
            speaking_timeout_seconds=0.1,
        )

        await fsm.start_thinking("test")
        await asyncio.sleep(0.15)

        assert fsm.state == SessionState.IDLE

    @pytest.mark.asyncio
    async def test_concurrent_gateway_requests(self):
        """Test concurrent Gateway request handling."""
        protocol = GatewayRPCProtocol()

        results = []

        async def long_handler(data):
            await asyncio.sleep(0.05)
            results.append(data.get("message"))
            return {"success": True}

        protocol.register_handler("voice.process", long_handler)

        tasks = [
            protocol.handle_request("voice.process", {"message": f"msg{i}"})
            for i in range(20)
        ]

        await asyncio.gather(*tasks)

        assert len(results) == 20


class TestResourceUsage:
    """Resource usage tests."""

    @pytest.mark.asyncio
    async def test_memory_usage_stable(self):
        """Test memory usage remains stable during operations."""
        import gc

        gc.collect()

        protocol = GatewayRPCProtocol()

        for i in range(100):
            await protocol.handle_request("chat.send", {
                "sessionKey": f"mem:test{i}",
                "message": f"Message {i}",
            })

        gc.collect()

        sessions_count = len(protocol._sessions)

        assert sessions_count <= 100

    @pytest.mark.asyncio
    async def test_session_cleanup(self):
        """Test old sessions are cleaned up."""
        protocol = GatewayRPCProtocol()

        for i in range(50):
            await protocol.handle_request("chat.inject", {
                "sessionKey": f"cleanup:test{i}",
                "role": "user",
                "content": f"Message {i}",
            })

        await protocol.clear_session("cleanup:test0")

        assert "cleanup:test0" not in protocol._sessions


class TestLoadScenarios:
    """Load scenario tests."""

    @pytest.mark.asyncio
    async def test_burst_message_handling(self):
        """Test handling burst of messages."""
        protocol = GatewayRPCProtocol()

        mock_process = AsyncMock(return_value="Response")
        protocol._process_message = mock_process

        burst_size = 100

        tasks = [
            protocol.handle_request("chat.send", {
                "sessionKey": f"burst:test{i}",
                "message": f"Burst message {i}",
            })
            for i in range(burst_size)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if isinstance(r, dict) and "runId" in r)

        assert success_count >= burst_size * 0.9

    @pytest.mark.asyncio
    async def test_sustained_load(self):
        """Test sustained load over time."""
        protocol = GatewayRPCProtocol()

        mock_process = AsyncMock(return_value="Response")
        protocol._process_message = mock_process

        duration_seconds = 2
        start_time = time.time()
        message_count = 0

        while time.time() - start_time < duration_seconds:
            await protocol.handle_request("chat.send", {
                "sessionKey": f"load:test{message_count}",
                "message": f"Load test {message_count}",
            })
            message_count += 1

        elapsed = time.time() - start_time
        throughput = message_count / elapsed

        assert throughput > 5, f"Sustained load throughput too low: {throughput:.2f} msg/s"


class TestLatencyBreakdown:
    """Detailed latency breakdown tests."""

    @pytest.mark.asyncio
    async def test_component_latency_breakdown(self):
        """Test latency breakdown across components."""
        metrics = {}

        mock_provider = MockProvider(response="Test response", delay_ms=50)
        mock_agent_loop = MockAgentLoop(provider=mock_provider)

        bridge = OpenClawBridge(agent_loop=mock_agent_loop)

        t0 = time.perf_counter()
        await bridge.start()
        t1 = time.perf_counter()
        metrics["bridge_start"] = (t1 - t0) * 1000

        t0 = time.perf_counter()
        async for _ in bridge.run("Test latency"):
            pass
        t1 = time.perf_counter()
        metrics["agent_process"] = (t1 - t0) * 1000

        await bridge.stop()

        assert metrics["bridge_start"] < 100
        assert metrics["agent_process"] < 500
