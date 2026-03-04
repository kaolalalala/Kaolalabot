"""Voice Activity Detection (VAD) module for detecting speech."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import AsyncIterator

import numpy as np


class VADEventType(Enum):
    """VAD event types."""

    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    SPEECHING = "speeching"
    SILENCE = "silence"


@dataclass
class VADEvent:
    """Voice Activity Detection event."""

    event_type: VADEventType
    timestamp_ms: int
    frame_index: int
    energy: float | None = None


class VADBackend(ABC):
    """Abstract base class for VAD backends."""

    @abstractmethod
    def process(self, audio_data: np.ndarray) -> VADEvent | None:
        """Process audio frame and return VAD event if any."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset VAD state."""
        pass


class WebRTCVAD(VADBackend):
    """
    WebRTC-based Voice Activity Detection.

    Uses webrtcvad for robust voice activity detection.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        aggressiveness: int = 3,
        frame_duration_ms: int = 20,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 500,
        speech_timeout_ms: int = 3000,
        energy_threshold: float = 500.0,
    ):
        """
        Initialize WebRTC VAD.

        Args:
            sample_rate: Audio sample rate (8000, 16000, 32000, or 48000)
            aggressiveness: VAD aggressiveness (0-3, higher = more sensitive)
            frame_duration_ms: Frame duration in ms (10, 20, or 30)
        """
        self.sample_rate = sample_rate
        self.aggressiveness = aggressiveness
        self.frame_duration_ms = frame_duration_ms

        try:
            import webrtcvad

            self._vad = webrtcvad.Vad(aggressiveness)
            self._vad.set_mode(aggressiveness)
        except ImportError:
            raise RuntimeError(
                "webrtcvad not installed. Install with: pip install webrtcvad"
            )

        self._is_speaking = False
        self._speech_start_time_ms = 0
        self._min_speech_duration_ms = min_speech_duration_ms
        self._min_silence_duration_ms = min_silence_duration_ms
        self._silence_counter = 0
        self._speech_timeout_ms = speech_timeout_ms
        self._energy_threshold = energy_threshold

    def process(self, audio_data: np.ndarray) -> VADEvent | None:
        """Process audio frame and detect voice activity."""
        if len(audio_data) == 0:
            return None

        if audio_data.dtype != np.int16:
            audio_data = (audio_data * 32767).astype(np.int16)

        audio_bytes = audio_data.tobytes()

        try:
            is_speech = self._vad.is_speech(audio_bytes, self.sample_rate)
        except Exception:
            is_speech = self._audio_energy_detect(audio_data)

        timestamp_ms = 0
        frame_index = 0
        energy = float(np.sqrt(np.mean(audio_data.astype(np.float32) ** 2)))

        if is_speech:
            self._silence_counter = 0

            if not self._is_speaking:
                self._is_speaking = True
                self._speech_start_time_ms = timestamp_ms
                return VADEvent(
                    event_type=VADEventType.SPEECH_START,
                    timestamp_ms=timestamp_ms,
                    frame_index=frame_index,
                    energy=energy,
                )
            else:
                return VADEvent(
                    event_type=VADEventType.SPEECHING,
                    timestamp_ms=timestamp_ms,
                    frame_index=frame_index,
                    energy=energy,
                )
        else:
            self._silence_counter += 1

            if self._is_speaking:
                silence_duration_ms = self._silence_counter * self.frame_duration_ms

                if silence_duration_ms >= self._min_silence_duration_ms:
                    self._is_speaking = False
                    self._silence_counter = 0
                    return VADEvent(
                        event_type=VADEventType.SPEECH_END,
                        timestamp_ms=timestamp_ms,
                        frame_index=frame_index,
                        energy=energy,
                    )

            return VADEvent(
                event_type=VADEventType.SILENCE,
                timestamp_ms=timestamp_ms,
                frame_index=frame_index,
                energy=energy,
            )

    def _audio_energy_detect(self, audio_data: np.ndarray) -> bool:
        """Fallback energy-based voice detection."""
        if len(audio_data) == 0:
            return False

        rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
        return rms > self._energy_threshold

    def reset(self) -> None:
        """Reset VAD state."""
        self._is_speaking = False
        self._silence_counter = 0
        self._speech_start_time_ms = 0


class EnergyVAD(VADBackend):
    """
    Simple energy-based Voice Activity Detection.

    Fallback implementation when webrtcvad is not available.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 20,
        energy_threshold: float = 500.0,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 500,
    ):
        """
        Initialize energy-based VAD.

        Args:
            sample_rate: Audio sample rate
            frame_duration_ms: Frame duration in ms
            energy_threshold: Energy threshold for speech detection
            min_speech_frames: Minimum consecutive speech frames
            min_silence_frames: Minimum consecutive silence frames
        """
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.energy_threshold = energy_threshold
        self.min_speech_frames = max(1, min_speech_duration_ms // frame_duration_ms)
        self.min_silence_frames = max(1, min_silence_duration_ms // frame_duration_ms)

        self._is_speaking = False
        self._consecutive_speech_frames = 0
        self._consecutive_silence_frames = 0

    def process(self, audio_data: np.ndarray) -> VADEvent | None:
        """Process audio frame using energy detection."""
        if len(audio_data) == 0:
            return None

        timestamp_ms = 0
        frame_index = 0

        energy = float(np.sqrt(np.mean(audio_data.astype(np.float32) ** 2)))

        is_speech = energy > self.energy_threshold

        if is_speech:
            self._consecutive_silence_frames = 0
            self._consecutive_speech_frames += 1

            if not self._is_speaking and self._consecutive_speech_frames >= self.min_speech_frames:
                self._is_speaking = True
                return VADEvent(
                    event_type=VADEventType.SPEECH_START,
                    timestamp_ms=timestamp_ms,
                    frame_index=frame_index,
                    energy=energy,
                )
            elif self._is_speaking:
                return VADEvent(
                    event_type=VADEventType.SPEECHING,
                    timestamp_ms=timestamp_ms,
                    frame_index=frame_index,
                    energy=energy,
                )
        else:
            self._consecutive_speech_frames = 0
            self._consecutive_silence_frames += 1

            if self._is_speaking and self._consecutive_silence_frames >= self.min_silence_frames:
                self._is_speaking = False
                self._consecutive_silence_frames = 0
                return VADEvent(
                    event_type=VADEventType.SPEECH_END,
                    timestamp_ms=timestamp_ms,
                    frame_index=frame_index,
                    energy=energy,
                )
            elif not self._is_speaking:
                return VADEvent(
                    event_type=VADEventType.SILENCE,
                    timestamp_ms=timestamp_ms,
                    frame_index=frame_index,
                    energy=energy,
                )

        return None

    def reset(self) -> None:
        """Reset VAD state."""
        self._is_speaking = False
        self._consecutive_speech_frames = 0
        self._consecutive_silence_frames = 0


class VAD:
    """
    Voice Activity Detection wrapper.

    Provides a unified interface for voice activity detection with
    async event streaming support.

    Usage:
        vad = VAD(sample_rate=16000, aggressiveness=3)
        async for event in vad.stream(audio_frames):
            if event.event_type == VADEventType.SPEECH_START:
                print("User started speaking")
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        aggressiveness: int = 3,
        frame_duration_ms: int = 20,
        backend: str = "webrtc",
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 500,
        speech_timeout_ms: int = 3000,
        energy_threshold: float = 500.0,
    ):
        """
        Initialize VAD.

        Args:
            sample_rate: Audio sample rate
            aggressiveness: VAD aggressiveness (0-3)
            frame_duration_ms: Frame duration in ms
            backend: VAD backend ('webrtc' or 'energy')
        """
        self.sample_rate = sample_rate
        self.aggressiveness = aggressiveness
        self.frame_duration_ms = frame_duration_ms

        if backend == "webrtc":
            try:
                self._backend = WebRTCVAD(
                    sample_rate=sample_rate,
                    aggressiveness=aggressiveness,
                    frame_duration_ms=frame_duration_ms,
                    min_speech_duration_ms=min_speech_duration_ms,
                    min_silence_duration_ms=min_silence_duration_ms,
                    speech_timeout_ms=speech_timeout_ms,
                    energy_threshold=energy_threshold,
                )
            except RuntimeError:
                self._backend = EnergyVAD(
                    sample_rate=sample_rate,
                    frame_duration_ms=frame_duration_ms,
                    energy_threshold=energy_threshold,
                    min_speech_duration_ms=min_speech_duration_ms,
                    min_silence_duration_ms=min_silence_duration_ms,
                )
        else:
            self._backend = EnergyVAD(
                sample_rate=sample_rate,
                frame_duration_ms=frame_duration_ms,
                energy_threshold=energy_threshold,
                min_speech_duration_ms=min_speech_duration_ms,
                min_silence_duration_ms=min_silence_duration_ms,
            )

        self._running = False

    def process(self, audio_data: np.ndarray) -> VADEvent | None:
        """
        Process a single audio frame.

        Args:
            audio_data: Audio data as numpy array

        Returns:
            VADEvent if state changed, None otherwise
        """
        return self._backend.process(audio_data)

    async def stream(
        self,
        audio_iterator: AsyncIterator[np.ndarray],
    ) -> AsyncIterator[VADEvent]:
        """
        Process audio stream and yield VAD events.

        Args:
            audio_iterator: Async iterator of audio frames

        Yields:
            VADEvent objects when voice activity state changes
        """
        self._running = True

        async for frame in audio_iterator:
            if not self._running:
                break

            event = self.process(frame)
            if event:
                yield event

    def reset(self) -> None:
        """Reset VAD state."""
        self._backend.reset()

    @property
    def is_speaking(self) -> bool:
        """Check if currently detecting speech."""
        if isinstance(self._backend, WebRTCVAD):
            return self._backend._is_speaking
        elif isinstance(self._backend, EnergyVAD):
            return self._backend._is_speaking
        return False
