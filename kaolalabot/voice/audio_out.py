"""Audio output module for playing audio through speakers."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

import numpy as np


@dataclass
class AudioChunk:
    """Audio chunk for playback."""

    data: bytes
    sample_rate: int
    channels: int = 1
    width: int = 2


class AudioOutBackend(ABC):
    """Abstract base class for audio output backends."""

    @abstractmethod
    async def start(self) -> None:
        """Start the audio output."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the audio output."""
        pass

    @abstractmethod
    async def play(self, audio_chunk: AudioChunk) -> None:
        """Play an audio chunk."""
        pass

    @abstractmethod
    async def flush(self) -> None:
        """Flush pending audio."""
        pass


class SoundDeviceOutBackend(AudioOutBackend):
    """SoundDevice-based audio output backend."""

    def __init__(
        self,
        sample_rate: int = 24000,
        channels: int = 1,
        device: int | None = None,
        blocksize: int = 1024,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.blocksize = blocksize
        self._stream = None
        self._running = False

    async def start(self) -> None:
        """Start the audio output."""
        import sounddevice as sd

        self._running = True
        self._stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            device=self.device,
            blocksize=self.blocksize,
            dtype="int16",
        )
        self._stream.start()

    async def stop(self) -> None:
        """Stop the audio output."""
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    async def play(self, audio_chunk: AudioChunk) -> None:
        """Play an audio chunk."""
        if not self._running or not self._stream:
            return

        try:
            import io
            import wave

            if audio_chunk.data.startswith(b"RIFF") and b"WAVE" in audio_chunk.data[:12]:
                wav_io = io.BytesIO(audio_chunk.data)
                with wave.open(wav_io, "rb") as wav:
                    frames = wav.readframes(wav.getnframes())
                    audio_data = np.frombuffer(frames, dtype=np.int16)
            else:
                audio_data = np.frombuffer(audio_chunk.data, dtype=np.int16)

            if len(audio_data) > 0:
                self._stream.write(audio_data)

        except Exception:
            pass

    async def flush(self) -> None:
        """Flush pending audio."""
        pass


class PyAudioOutBackend(AudioOutBackend):
    """PyAudio-based audio output backend."""

    def __init__(
        self,
        sample_rate: int = 24000,
        channels: int = 1,
        device: int | None = None,
        blocksize: int = 1024,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.blocksize = blocksize
        self._stream = None
        self._running = False
        self._pyaudio = None

    async def start(self) -> None:
        """Start the audio output."""
        import pyaudio

        self._pyaudio = pyaudio.PyAudio()
        self._running = True
        self._stream = self._pyaudio.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            output=True,
            output_device_index=self.device,
            frames_per_buffer=self.blocksize,
        )

    async def stop(self) -> None:
        """Stop the audio output."""
        self._running = False
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._pyaudio:
            self._pyaudio.terminate()

    async def play(self, audio_chunk: AudioChunk) -> None:
        """Play an audio chunk."""
        if not self._running or not self._stream:
            return

        try:
            import io
            import wave

            if audio_chunk.data.startswith(b"RIFF") and b"WAVE" in audio_chunk.data[:12]:
                wav_io = io.BytesIO(audio_chunk.data)
                with wave.open(wav_io, "rb") as wav:
                    frames = wav.readframes(wav.getnframes())
                    self._stream.write(frames)
            else:
                self._stream.write(audio_chunk.data)

        except Exception:
            pass

    async def flush(self) -> None:
        """Flush pending audio."""
        pass


class AudioOut:
    """
    Audio output handler for playing synthesized speech.

    Provides streaming audio playback with interrupt capability.

    Usage:
        audio_out = AudioOut(sample_rate=24000)
        await audio_out.start()
        await audio_out.play_chunk(audio_data)
        await audio_out.stop()
    """

    def __init__(
        self,
        sample_rate: int = 24000,
        channels: int = 1,
        backend: str = "sounddevice",
        device: int | None = None,
    ):
        """
        Initialize audio output.

        Args:
            sample_rate: Output sample rate
            channels: Number of audio channels
            backend: Audio backend ('sounddevice' or 'pyaudio')
            device: Audio device index
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device

        self._backend: AudioOutBackend | None = None
        self._backend_type = backend
        self._running = False
        self._playing = False

    def _create_backend(self) -> AudioOutBackend:
        """Create the appropriate audio backend."""
        if self._backend_type == "sounddevice":
            try:
                return SoundDeviceOutBackend(
                    sample_rate=self.sample_rate,
                    channels=self.channels,
                    device=self.device,
                )
            except ImportError:
                pass

        if self._backend_type == "pyaudio":
            try:
                return PyAudioOutBackend(
                    sample_rate=self.sample_rate,
                    channels=self.channels,
                    device=self.device,
                )
            except ImportError:
                pass

        raise RuntimeError(
            f"No available audio backend. Install sounddevice or pyaudio."
        )

    async def start(self) -> None:
        """Start audio output."""
        if self._running:
            return

        self._backend = self._create_backend()
        await self._backend.start()
        self._running = True

    async def stop(self) -> None:
        """Stop audio output."""
        if not self._running:
            return

        self._running = False
        self._playing = False
        if self._backend:
            await self._backend.stop()
            self._backend = None

    async def play_chunk(self, audio_data: bytes) -> None:
        """
        Play a single audio chunk.

        Args:
            audio_data: Raw audio bytes
        """
        if not self._running or not self._backend:
            return

        self._playing = True
        chunk = AudioChunk(
            data=audio_data,
            sample_rate=self.sample_rate,
            channels=self.channels,
        )
        await self._backend.play(chunk)
        self._playing = False

    async def play_stream(
        self,
        audio_iterator: AsyncIterator[bytes],
    ) -> None:
        """
        Play audio from an async iterator.

        Args:
            audio_iterator: Async iterator of audio chunks
        """
        if not self._running:
            await self.start()

        self._playing = True

        try:
            async for audio_data in audio_iterator:
                if not self._running:
                    break
                await self.play_chunk(audio_data)
        finally:
            self._playing = False

    async def flush(self) -> None:
        """Flush pending audio."""
        if self._backend:
            await self._backend.flush()

    @property
    def is_running(self) -> bool:
        """Check if audio output is running."""
        return self._running

    @property
    def is_playing(self) -> bool:
        """Check if currently playing audio."""
        return self._playing
