"""TTS (Text-to-Speech) stream interface."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Awaitable, Callable


@dataclass
class TTSAudioChunk:
    """TTS audio chunk data."""

    data: bytes
    text: str
    index: int
    is_final: bool


class TTSStream(ABC):
    """Abstract base class for streaming TTS."""

    @abstractmethod
    async def start(self) -> None:
        """Start the TTS engine."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the TTS engine."""
        pass

    @abstractmethod
    async def speak_stream(
        self,
        text_iterator: AsyncIterator[str],
    ) -> AsyncIterator[TTSAudioChunk]:
        """
        Speak text from an async iterator.

        Args:
            text_iterator: Async iterator of text chunks

        Yields:
            TTSAudioChunk objects with audio data
        """
        pass

    @abstractmethod
    async def speak(self, text: str) -> bytes:
        """
        Speak text and return complete audio.

        Args:
            text: Text to speak

        Returns:
            Complete audio data as bytes
        """
        pass

    @property
    @abstractmethod
    def is_speaking(self) -> bool:
        """Check if TTS is currently speaking."""
        pass


class ChunkStrategy:
    """Strategy for splitting text into TTS chunks."""

    PUNCTUATION_END = {"。", "！", "？", "；", ".", "!", "?", ";", "\n"}
    PUNCTUATION_PAUSE = {",", "，", "、", ",", "、"}

    @staticmethod
    def should_flush(text: str, char_count: int, last_flush_time: float) -> bool:
        """
        Determine if we should flush (synthesize) the current buffer.

        Args:
            text: Current text buffer
            char_count: Number of characters in buffer
            last_flush_time: Timestamp of last flush

        Returns:
            True if should flush now
        """
        import time

        if not text:
            return False

        last_char = text[-1]

        if last_char in ChunkStrategy.PUNCTUATION_END:
            return True

        if char_count >= 60:
            return True

        if last_flush_time > 0:
            elapsed = time.time() - last_flush_time
            if elapsed > 0.8:
                return True

        return False

    @staticmethod
    async def split_into_chunks(
        text: str,
        max_chars: int = 50,
        chunk_interval_ms: int = 800,
    ) -> AsyncIterator[str]:
        """
        Split text into chunks for streaming synthesis.

        Args:
            text: Input text
            max_chars: Maximum characters per chunk
            chunk_interval_ms: Maximum time between chunks

        Yields:
            Text chunks
        """
        import time

        buffer = ""
        last_flush = time.time()

        for char in text:
            buffer += char

            if ChunkStrategy.should_flush(buffer, len(buffer), last_flush):
                yield buffer
                buffer = ""
                last_flush = time.time()
            await asyncio.sleep(0)

        if buffer:
            yield buffer
