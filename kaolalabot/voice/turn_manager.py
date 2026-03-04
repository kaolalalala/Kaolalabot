"""Turn Manager for handling barge-in and turn-taking in voice conversations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Callable, Awaitable
import uuid


@dataclass
class TurnContext:
    """Context for a conversation turn."""

    turn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_speaking: bool = False
    agent_speaking: bool = False
    agent_thinking: bool = False
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class TurnManager:
    """
    Turn Manager for managing conversation turns and barge-in.

    This module handles:
    - Creating and managing conversation turns
    - Detecting and handling barge-in (user interrupting agent)
    - Coordinating cancellation across ASR, TTS, and Agent components
    - Clearing output queues on interrupt

    The barge-in flow:
    1. User starts speaking (VAD detects SPEECH_START)
    2. TurnManager.barge_in() is called
    3. TurnManager stops: TTS playback, AudioOut, Agent processing
    4. Clears all pending output queues
    5. Creates a new turn for the user input
    """

    def __init__(
        self,
        enabled: bool = True,
        barge_in_on_speech_start: bool = True,
        interrupt_on_speech_start: bool = True,
        clear_queue_on_barge_in: bool = True,
    ):
        """
        Initialize TurnManager.

        Args:
            enabled: Whether turn management is enabled
            barge_in_on_speech_start: Trigger barge-in on speech start
            interrupt_on_speech_start: Interrupt current processing on speech start
            clear_queue_on_barge_in: Clear output queues on barge-in
        """
        self.enabled = enabled
        self.barge_in_on_speech_start = barge_in_on_speech_start
        self.interrupt_on_speech_start = interrupt_on_speech_start
        self.clear_queue_on_barge_in = clear_queue_on_barge_in

        self._current_turn: TurnContext = TurnContext()
        self._cancel_callbacks: list[Callable[[], Awaitable[None]]] = []
        self._queue_clear_callbacks: list[Callable[[], Awaitable[None]]] = []
        self._lock = asyncio.Lock()

    def register_cancel_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        """
        Register a callback to be called when barge-in occurs.

        The callback should cancel the current operation (TTS, ASR, Agent).

        Args:
            callback: Async callback function
        """
        self._cancel_callbacks.append(callback)

    def register_queue_clear_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        """
        Register a callback to clear output queues on barge-in.

        Args:
            callback: Async callback function
        """
        self._queue_clear_callbacks.append(callback)

    async def barge_in(self) -> None:
        """
        Handle barge-in (user interruption).

        This is called when:
        - VAD detects SPEECH_START while agent is speaking/thinking
        - User explicitly interrupts

        Actions:
        1. Call all cancel callbacks to stop TTS, ASR, Agent
        2. Call all queue clear callbacks
        3. Create a new turn for user input
        """
        if not self.enabled:
            return

        async with self._lock:
            if not self.interrupt_on_speech_start:
                return

            for callback in self._cancel_callbacks:
                try:
                    await callback()
                except Exception:
                    pass

            if self.clear_queue_on_barge_in:
                for callback in self._queue_clear_callbacks:
                    try:
                        await callback()
                    except Exception:
                        pass

            await self.new_turn()

    async def new_turn(self) -> TurnContext:
        """
        Create a new conversation turn.

        Returns:
            The new turn context
        """
        async with self._lock:
            self._current_turn = TurnContext()
            return self._current_turn

    def get_current_turn(self) -> TurnContext:
        """Get the current turn context."""
        return self._current_turn

    def set_user_speaking(self, speaking: bool) -> None:
        """Update user speaking state."""
        self._current_turn.user_speaking = speaking

    def set_agent_speaking(self, speaking: bool) -> None:
        """Update agent speaking state."""
        self._current_turn.agent_speaking = speaking

    def set_agent_thinking(self, thinking: bool) -> None:
        """Update agent thinking state."""
        self._current_turn.agent_thinking = thinking

    def should_barge_in(self) -> bool:
        """
        Check if barge-in should be triggered.

        Returns True if:
        - Agent is currently speaking or thinking
        - Turn management is enabled

        Returns:
            Whether barge-in should occur
        """
        if not self.enabled:
            return False

        return (
            self._current_turn.agent_speaking
            or self._current_turn.agent_thinking
        )

    @property
    def is_user_speaking(self) -> bool:
        """Check if user is currently speaking."""
        return self._current_turn.user_speaking

    @property
    def is_agent_speaking(self) -> bool:
        """Check if agent is currently speaking."""
        return self._current_turn.agent_speaking

    @property
    def is_agent_thinking(self) -> bool:
        """Check if agent is currently thinking."""
        return self._current_turn.agent_thinking
