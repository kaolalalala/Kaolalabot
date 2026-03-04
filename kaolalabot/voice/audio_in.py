"""Audio input module for capturing microphone audio frames."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

import numpy as np


@dataclass
class AudioFrame:
    """Represents a single audio frame."""

    data: np.ndarray
    sample_rate: int
    timestamp_ms: int
    frame_index: int


class AudioInBackend(ABC):
    """Abstract base class for audio input backends."""

    @abstractmethod
    async def start(self) -> None:
        """Start audio capture."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop audio capture."""
        pass

    @abstractmethod
    async def read(self) -> np.ndarray | None:
        """Read a single audio frame. Returns None if stopped."""
        pass

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Get the sample rate."""
        pass

    @property
    @abstractmethod
    def channels(self) -> int:
        """Get the number of channels."""
        pass


class SoundDeviceBackend(AudioInBackend):
    """SoundDevice-based audio input backend."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        blocksize: int = 320,
        device: int | None = None,
    ):
        self._sample_rate = sample_rate
        self._channels = channels
        self.blocksize = blocksize
        self.device = device
        self._stream = None
        self._running = False
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue()
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start audio capture."""
        import sounddevice as sd

        self._running = True

        def callback(indata, frames, time, status):
            if status:
                return
            if self._running:
                try:
                    self._queue.put_nowait(indata[:, 0].copy())
                except asyncio.QueueFull:
                    pass

        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            blocksize=self.blocksize,
            device=self.device,
            dtype="int16",
            callback=callback,
        )
        self._stream.start()

    async def stop(self) -> None:
        """Stop audio capture."""
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    async def read(self) -> np.ndarray | None:
        """Read a single audio frame."""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def channels(self) -> int:
        return self._channels


class PyAudioBackend(AudioInBackend):
    """PyAudio-based audio input backend."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        blocksize: int = 320,
        device: int | None = None,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        self.device = device
        self._stream = None
        self._running = False
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue()

    async def start(self) -> None:
        """Start audio capture."""
        import pyaudio

        self._running = True
        self._pyaudio = pyaudio.PyAudio()

        def callback(in_data, frame_count, time_info, status):
            if status:
                return None
            if self._running:
                data = np.frombuffer(in_data, dtype=np.int16)
                try:
                    self._queue.put_nowait(data)
                except asyncio.QueueFull:
                    pass
            return None

        self._stream = self._pyaudio.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            input_device_index=self.device,
            frames_per_buffer=self.blocksize,
            stream_callback=callback,
        )

    async def stop(self) -> None:
        """Stop audio capture."""
        self._running = False
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if hasattr(self, "_pyaudio"):
            self._pyaudio.terminate()

    async def read(self) -> np.ndarray | None:
        """Read a single audio frame."""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None

    @property
    def sample_rate(self) -> int:
        return self.sample_rate

    @property
    def channels(self) -> int:
        return self.channels


class AudioIn:
    """
    Audio input handler that captures audio frames from microphone.

    Provides an async iterator interface for streaming audio frames.

    Usage:
        async with AudioIn(sample_rate=16000) as audio_in:
            async for frame in audio_in.frames():
                process(frame)
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 20,
        channels: int = 1,
        backend: str = "sounddevice",
        device: int | None = None,
    ):
        """
        Initialize audio input.

        Args:
            sample_rate: Sample rate in Hz (default: 16000)
            frame_duration_ms: Frame duration in milliseconds (default: 20)
            channels: Number of audio channels (default: 1 for mono)
            backend: Audio backend to use ('sounddevice' or 'pyaudio')
            device: Audio device index (None for default)
        """
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.channels = channels
        self.blocksize = int(sample_rate * frame_duration_ms / 1000)
        self.device = device

        self._backend: AudioInBackend | None = None
        self._backend_type = backend
        self._running = False
        self._frame_index = 0
        self._start_timestamp_ms = 0

    def _create_backend(self) -> AudioInBackend:
        """Create the appropriate audio backend."""
        if self._backend_type == "sounddevice":
            try:
                return SoundDeviceBackend(
                    sample_rate=self.sample_rate,
                    channels=self.channels,
                    blocksize=self.blocksize,
                    device=self.device,
                )
            except ImportError:
                pass

        if self._backend_type == "pyaudio":
            try:
                return PyAudioBackend(
                    sample_rate=self.sample_rate,
                    channels=self.channels,
                    blocksize=self.blocksize,
                    device=self.device,
                )
            except ImportError:
                pass

        raise RuntimeError(
            f"No available audio backend. Install sounddevice or pyaudio: "
            f"pip install sounddevice  # or pip install pyaudio"
        )

    async def start(self) -> None:
        """Start audio capture."""
        if self._running:
            return

        self._backend = self._create_backend()
        await self._backend.start()
        self._running = True
        self._frame_index = 0
        import time

        self._start_timestamp_ms = int(time.time() * 1000)

    async def stop(self) -> None:
        """Stop audio capture."""
        if not self._running:
            return

        self._running = False
        if self._backend:
            await self._backend.stop()
            self._backend = None

    async def frames(self) -> AsyncIterator[AudioFrame]:
        """
        Yield audio frames continuously.

        Yields:
            AudioFrame objects containing audio data and metadata

        Example:
            async with AudioIn() as audio_in:
                async for frame in audio_in.frames():
                    vad.process(frame.data)
        """
        if not self._running:
            await self.start()

        while self._running:
            if self._backend:
                data = await self._backend.read()
                if data is not None:
                    yield AudioFrame(
                        data=data,
                        sample_rate=self.sample_rate,
                        timestamp_ms=self._start_timestamp_ms
                        + self._frame_index * self.frame_duration_ms,
                        frame_index=self._frame_index,
                    )
                    self._frame_index += 1
            await asyncio.sleep(0.001)

    async def __aenter__(self) -> "AudioIn":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()

    @property
    def is_running(self) -> bool:
        """Check if audio capture is running."""
        return self._running
