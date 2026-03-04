"""Test fixtures and utilities for voice module testing."""

import asyncio
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest


@dataclass
class AudioTestData:
    """Test audio data container."""

    sample_rate: int = 16000
    duration_ms: int = 1000
    frequency: float = 440.0
    amplitude: float = 0.5

    def generate_silence(self, duration_ms: int = 1000) -> np.ndarray:
        """Generate silent audio."""
        samples = int(self.sample_rate * duration_ms / 1000)
        return np.zeros(samples, dtype=np.int16)

    def generate_tone(self, duration_ms: int | None = None) -> np.ndarray:
        """Generate a pure tone for testing."""
        duration = duration_ms or self.duration_ms
        samples = int(self.sample_rate * duration / 1000)
        t = np.linspace(0, duration / 1000, samples)
        audio = (self.amplitude * np.sin(2 * np.pi * self.frequency * t) * 32767).astype(np.int16)
        return audio

    def generate_speech_like(self, duration_ms: int = 1000) -> np.ndarray:
        """Generate speech-like audio with varying energy."""
        duration = duration_ms or self.duration_ms
        samples = int(self.sample_rate * duration / 1000)
        t = np.linspace(0, duration / 1000, samples)
        envelope = np.exp(-((t - duration / 2000) ** 2) / (2 * (duration / 4000) ** 2))
        audio = (self.amplitude * envelope * (
            0.5 * np.sin(2 * np.pi * 200 * t) +
            0.3 * np.sin(2 * np.pi * 400 * t) +
            0.2 * np.sin(2 * np.pi * 600 * t)
        ) * 32767).astype(np.int16)
        return audio


@dataclass
class TestMetrics:
    """Container for test metrics."""

    start_time: float = 0
    end_time: float = 0
    latency_ms: float = 0
    errors: list[str] = field(default_factory=list)
    data_points: dict[str, Any] = field(default_factory=dict)

    def record_start(self) -> None:
        """Record start time."""
        import time
        self.start_time = time.perf_counter()

    def record_end(self) -> None:
        """Record end time and calculate latency."""
        import time
        self.end_time = time.perf_counter()
        self.latency_ms = (self.end_time - self.start_time) * 1000

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "latency_ms": self.latency_ms,
            "errors": self.errors,
            "data_points": self.data_points,
        }


class MockProvider:
    """Mock LLM provider for testing."""

    def __init__(self, response: str = "测试回复", delay_ms: int = 0):
        self.response = response
        self.delay_ms = delay_ms
        self.call_count = 0
        self.last_messages: list[dict] = []

    async def chat(self, messages: list[dict], **kwargs) -> MagicMock:
        """Mock chat method."""
        self.call_count += 1
        self.last_messages = messages

        if self.delay_ms > 0:
            await asyncio.sleep(self.delay_ms / 1000)

        mock_response = MagicMock()
        mock_response.content = self.response
        mock_response.has_tool_calls = False
        mock_response.reasoning_content = None
        mock_response.thinking_blocks = []
        return mock_response


class MockAgentLoop:
    """Mock AgentLoop for testing."""

    def __init__(self, provider: MockProvider | None = None):
        self.provider = provider or MockProvider()
        self.processed_messages: list[str] = []
        self.session_keys: list[str] = []

    async def process_direct(
        self,
        content: str,
        session_key: str = "test:session",
        channel: str = "test",
        chat_id: str = "test",
        on_progress=None,
    ) -> str:
        """Mock process_direct method."""
        self.processed_messages.append(content)
        self.session_keys.append(session_key)

        if on_progress:
            await on_progress("processing...")

        response = await self.provider.chat([{"role": "user", "content": content}])
        return response.content


class MockMessageBus:
    """Mock MessageBus for testing."""

    def __init__(self):
        self.inbound_messages: list = []
        self.outbound_messages: list = []
        self._inbound_queue: asyncio.Queue | None = None

    async def consume_inbound(self):
        """Mock consume inbound."""
        if self._inbound_queue:
            return await self._inbound_queue.get()
        await asyncio.sleep(0.01)
        raise asyncio.TimeoutError()

    async def publish_inbound(self, msg):
        """Mock publish inbound."""
        self.inbound_messages.append(msg)

    async def publish_outbound(self, msg):
        """Mock publish outbound."""
        self.outbound_messages.append(msg)


@pytest.fixture
def audio_generator():
    """Fixture providing audio test data generator."""
    return AudioTestData()


@pytest.fixture
def mock_provider():
    """Fixture providing mock LLM provider."""
    return MockProvider()


@pytest.fixture
def mock_agent_loop(mock_provider):
    """Fixture providing mock AgentLoop."""
    return MockAgentLoop(provider=mock_provider)


@pytest.fixture
def mock_message_bus():
    """Fixture providing mock MessageBus."""
    return MockMessageBus()


@pytest.fixture
def test_metrics():
    """Fixture providing test metrics container."""
    return TestMetrics()
