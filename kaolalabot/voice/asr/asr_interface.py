"""ASR (Automatic Speech Recognition) stream interface."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Awaitable, Callable


@dataclass
class ASRResult:
    """ASR recognition result."""

    text: str
    is_final: bool
    confidence: float | None = None


class ASRStream(ABC):
    """Abstract base class for streaming ASR."""

    @abstractmethod
    async def start(self) -> None:
        """Start the ASR stream."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the ASR stream."""
        pass

    @abstractmethod
    async def push_audio(self, audio_data: bytes) -> None:
        """Push audio data to the ASR stream."""
        pass

    @abstractmethod
    async def finalize(self) -> str | None:
        """Force finalization and return final text."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset the ASR state."""
        pass

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """Check if ASR is running."""
        pass


class ASREventHandler:
    """Handler for ASR events."""

    def __init__(
        self,
        on_partial: Callable[[str], Awaitable[None]] | None = None,
        on_final: Callable[[str], Awaitable[None]] | None = None,
    ):
        self.on_partial = on_partial
        self.on_final = on_final

    async def handle_partial(self, text: str) -> None:
        """Handle partial recognition result."""
        if self.on_partial:
            await self.on_partial(text)

    async def handle_final(self, text: str) -> None:
        """Handle final recognition result."""
        if self.on_final:
            await self.on_final(text)
