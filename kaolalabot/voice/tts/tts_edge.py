"""Edge TTS (Text-to-Speech) streaming implementation."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import numpy as np

from .tts_interface import TTSStream, TTSAudioChunk, ChunkStrategy


class EdgeTTSStream(TTSStream):
    """
    Edge TTS streaming implementation.

    Uses Microsoft Edge's TTS service for high-quality speech synthesis.
    Simple to use, good quality, but requires network connection.

    Features:
    - Streaming synthesis with chunk-by-chunk playback
    - Interruptible playback (stop() cancels synthesis)
    - Multiple voice options
    """

    def __init__(
        self,
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: str = "+0%",
        pitch: str = "+0Hz",
        volume: str = "+0%",
        output_format: str = "audio-24khz-48kbitrate-mono-mp3",
        max_chars_per_chunk: int = 50,
        chunk_interval_ms: int = 800,
    ):
        """
        Initialize Edge TTS.

        Args:
            voice: Voice name (e.g., 'zh-CN-XiaoxiaoNeural')
            rate: Speech rate (e.g., '+0%', '+50%', '-50%')
            pitch: Pitch adjustment (e.g., '+0Hz', '+5Hz')
            volume: Volume adjustment (e.g., '+0%', '+50%')
            output_format: Output audio format
            max_chars_per_chunk: Maximum characters per chunk
            chunk_interval_ms: Maximum interval between chunks
        """
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        self.output_format = output_format
        self.max_chars_per_chunk = max_chars_per_chunk
        self.chunk_interval_ms = chunk_interval_ms

        self._running = False
        self._speaking = False
        self._current_task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None

    async def start(self) -> None:
        """Start the TTS engine."""
        self._running = True

    async def stop(self) -> None:
        """Stop current speech synthesis and playback."""
        self._running = False
        self._speaking = False

        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass

        if self._stop_event:
            self._stop_event.set()

    async def speak_stream(
        self,
        text_iterator: AsyncIterator[str],
    ) -> AsyncIterator[TTSAudioChunk]:
        """
        Speak text from an async iterator with streaming audio.

        This implements the "chunk strategy" for natural-sounding streaming:
        - Buffer text until sentence end OR char threshold OR timeout
        - Synthesize each chunk immediately
        - Yield audio chunks for playback

        Args:
            text_iterator: Async iterator of text chunks

        Yields:
            TTSAudioChunk objects with audio data
        """
        if not self._running:
            return

        self._speaking = True
        self._stop_event = asyncio.Event()

        buffer = ""
        chunk_index = 0

        try:
            async for text_chunk in text_iterator:
                if not self._running:
                    break

                buffer += text_chunk

                while len(buffer) >= 10:
                    should_flush = ChunkStrategy.should_flush(
                        buffer,
                        len(buffer),
                        0,
                    )

                    if should_flush or len(buffer) >= self.max_chars_per_chunk:
                        flush_point = self._find_flush_point(buffer)

                        if flush_point > 0:
                            chunk_text = buffer[:flush_point]
                            buffer = buffer[flush_point:]

                            audio_data = await self._synthesize_chunk(chunk_text)

                            if audio_data:
                                yield TTSAudioChunk(
                                    data=audio_data,
                                    text=chunk_text,
                                    index=chunk_index,
                                    is_final=False,
                                )
                                chunk_index += 1
                        else:
                            break

                    if not should_flush and len(buffer) < self.max_chars_per_chunk:
                        break

            if buffer.strip():
                audio_data = await self._synthesize_chunk(buffer)
                if audio_data:
                    yield TTSAudioChunk(
                        data=audio_data,
                        text=buffer,
                        index=chunk_index,
                        is_final=True,
                    )

        except asyncio.CancelledError:
            pass
        finally:
            self._speaking = False
            self._stop_event = None

    def _find_flush_point(self, text: str) -> int:
        """Find the best point to split text for natural speech."""
        if not text:
            return 0

        end_punct = {"。", "！", "？", "；", ".", "!", "?", ";", "\n"}
        pause_punct = {",", "，", "、", ",", "、"}

        for i in range(len(text) - 1, -1, -1):
            if text[i] in end_punct:
                return i + 1
            if text[i] in pause_punct and i > self.max_chars_per_chunk // 2:
                return i + 1

        if len(text) >= self.max_chars_per_chunk:
            return min(len(text), self.max_chars_per_chunk)

        return 0

    async def _synthesize_chunk(self, text: str) -> bytes | None:
        """Synthesize a single text chunk."""
        if not text.strip():
            return None

        try:
            import edge_tts

            communicate = edge_tts.Communicate(
                text,
                self.voice,
                rate=self.rate,
                pitch=self.pitch,
                volume=self.volume,
            )

            audio_data = b""
            async for message in communicate.stream():
                if message["type"] == "audio":
                    audio_data += message["data"]
                elif message["type"] == "WordBoundary":
                    pass

            return audio_data if audio_data else None

        except ImportError:
            raise RuntimeError(
                "edge-tts not installed. Install with: pip install edge-tts"
            )
        except Exception:
            return None

    async def speak(self, text: str) -> bytes:
        """
        Speak text and return complete audio.

        Args:
            text: Text to speak

        Returns:
            Complete audio data as bytes
        """
        if not self._running:
            await self.start()

        async def text_iter():
            yield text

        chunks = []
        async for chunk in self.speak_stream(text_iter()):
            chunks.append(chunk.data)

        return b"".join(chunks)

    @property
    def is_speaking(self) -> bool:
        """Check if TTS is currently speaking."""
        return self._speaking


class LocalTTSStream(TTSStream):
    """
    Local TTS using Coqui XTTS or similar.

    This is for future expansion when local TTS is needed.
    Currently a placeholder for XTTS/CosyVoice integration.
    """

    def __init__(
        self,
        model_path: str | None = None,
        device: str = "cuda",
    ):
        """
        Initialize local TTS.

        Args:
            model_path: Path to TTS model
            device: Device to use ('cuda' or 'cpu')
        """
        self.model_path = model_path
        self.device = device

        self._running = False
        self._speaking = False

    async def start(self) -> None:
        """Start the TTS engine."""
        raise NotImplementedError("Local TTS not yet implemented")

    async def stop(self) -> None:
        """Stop current speech synthesis."""
        self._speaking = False

    async def speak_stream(
        self,
        text_iterator: AsyncIterator[str],
    ) -> AsyncIterator[TTSAudioChunk]:
        """Speak text from an async iterator."""
        raise NotImplementedError("Local TTS not yet implemented")

    async def speak(self, text: str) -> bytes:
        """Speak text and return complete audio."""
        raise NotImplementedError("Local TTS not yet implemented")

    @property
    def is_speaking(self) -> bool:
        """Check if TTS is currently speaking."""
        return self._speaking
