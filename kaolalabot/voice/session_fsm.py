"""Session FSM (Finite State Machine) for managing voice conversation states."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Awaitable


class SessionState(Enum):
    """Voice session states."""

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    EXECUTING = "executing"
    WAITING_USER = "waiting_user"


class StateTransitionError(Exception):
    """Error raised when an invalid state transition occurs."""

    pass


@dataclass
class StateContext:
    """Context information for the current state."""

    state: SessionState
    previous_state: SessionState | None
    entered_at: datetime = field(default_factory=datetime.now)
    user_input: str | None = None
    agent_response: str | None = None
    tool_calls: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class StateCallbacks:
    """Callbacks for state changes."""

    def __init__(
        self,
        on_state_change: Callable[[SessionState, SessionState], Awaitable[None]] | None = None,
        on_enter: Callable[[SessionState], Awaitable[None]] | None = None,
        on_exit: Callable[[SessionState], Awaitable[None]] | None = None,
    ):
        self.on_state_change = on_state_change
        self.on_enter = on_enter
        self.on_exit = on_exit


class SessionFSM:
    """
    Session Finite State Machine for managing voice conversation flow.

    This FSM manages the conversation states and transitions:

    IDLE -> LISTENING: User starts speaking (VAD detects speech)
    LISTENING -> THINKING: User stops speaking (VAD detects silence) + ASR finalizes
    THINKING -> SPEAKING: Agent starts responding (first TTS chunk)
    SPEAKING -> LISTENING: User interrupts (barge-in)
    SPEAKING -> EXECUTING: Agent executes a tool
    EXECUTING -> SPEAKING: Tool execution completes
    SPEAKING -> IDLE: Agent finishes speaking
    SPEAKING -> WAITING_USER: Agent needs user confirmation

    Timeouts:
    - idle_timeout: Return to IDLE after this duration of silence
    - thinking_timeout: Maximum time for agent to think
    - speaking_timeout: Maximum time for agent to speak
    """

    VALID_TRANSITIONS: dict[SessionState, set[SessionState]] = {
        SessionState.IDLE: {SessionState.LISTENING, SessionState.THINKING, SessionState.SPEAKING},
        SessionState.LISTENING: {SessionState.THINKING, SessionState.IDLE, SessionState.SPEAKING},
        SessionState.THINKING: {SessionState.SPEAKING, SessionState.LISTENING, SessionState.IDLE},
        SessionState.SPEAKING: {
            SessionState.LISTENING,
            SessionState.EXECUTING,
            SessionState.IDLE,
            SessionState.WAITING_USER,
        },
        SessionState.EXECUTING: {SessionState.SPEAKING, SessionState.LISTENING, SessionState.IDLE},
        SessionState.WAITING_USER: {SessionState.LISTENING, SessionState.IDLE},
    }

    def __init__(
        self,
        idle_timeout_seconds: float = 300.0,
        thinking_timeout_seconds: float = 60.0,
        speaking_timeout_seconds: float = 120.0,
        allow_parallel_execution: bool = True,
    ):
        """
        Initialize SessionFSM.

        Args:
            idle_timeout_seconds: Timeout to return to IDLE after last activity
            thinking_timeout_seconds: Maximum time for agent to think
            speaking_timeout_seconds: Maximum time for agent to speak
            allow_parallel_execution: Allow tool execution while speaking
        """
        self.idle_timeout = idle_timeout_seconds
        self.thinking_timeout = thinking_timeout_seconds
        self.speaking_timeout = speaking_timeout_seconds
        self.allow_parallel_execution = allow_parallel_execution

        self._state = SessionState.IDLE
        self._previous_state: SessionState | None = None
        self._context = StateContext(
            state=SessionState.IDLE,
            previous_state=None,
        )
        self._callbacks = StateCallbacks()
        self._timeout_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> SessionState:
        """Get the current state."""
        return self._state

    @property
    def previous_state(self) -> SessionState | None:
        """Get the previous state."""
        return self._previous_state

    @property
    def context(self) -> StateContext:
        """Get the current state context."""
        return self._context

    def set_callbacks(self, callbacks: StateCallbacks) -> None:
        """Set state change callbacks."""
        self._callbacks = callbacks

    async def transition_to(self, new_state: SessionState) -> None:
        """
        Transition to a new state.

        Args:
            new_state: The state to transition to

        Raises:
            StateTransitionError: If the transition is not valid
        """
        async with self._lock:
            if new_state == self._state:
                return

            if new_state not in self.VALID_TRANSITIONS.get(self._state, set()):
                raise StateTransitionError(
                    f"Invalid transition from {self._state.value} to {new_state.value}"
                )

            old_state = self._state

            if self._callbacks.on_exit:
                await self._callbacks.on_exit(old_state)

            self._previous_state = self._state
            self._state = new_state
            self._context = StateContext(
                state=new_state,
                previous_state=old_state,
            )

            if self._callbacks.on_state_change:
                await self._callbacks.on_state_change(old_state, new_state)

            if self._callbacks.on_enter:
                await self._callbacks.on_enter(new_state)

            self._cancel_timeout()
            self._start_state_timeout(new_state)

    def _cancel_timeout(self) -> None:
        """Cancel any pending timeout."""
        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
            self._timeout_task = None

    def _start_state_timeout(self, state: SessionState) -> None:
        """Start a timeout for the current state."""
        timeout_map = {
            SessionState.IDLE: self.idle_timeout,
            SessionState.THINKING: self.thinking_timeout,
            SessionState.SPEAKING: self.speaking_timeout,
        }

        timeout = timeout_map.get(state)
        if timeout:
            loop = asyncio.get_event_loop()

            async def timeout_handler():
                await asyncio.sleep(timeout)
                await self.transition_to(SessionState.IDLE)

            self._timeout_task = loop.create_task(timeout_handler())

    async def start_listening(self) -> None:
        """Start listening state (user is speaking)."""
        await self.transition_to(SessionState.LISTENING)

    async def start_thinking(self, user_input: str | None = None) -> None:
        """Start thinking state (ASR finalized, agent is processing)."""
        self._context.user_input = user_input
        await self.transition_to(SessionState.THINKING)

    async def start_speaking(self, agent_response: str | None = None) -> None:
        """Start speaking state (TTS is playing)."""
        self._context.agent_response = agent_response
        await self.transition_to(SessionState.SPEAKING)

    async def start_executing(self, tool_calls: list[dict] | None = None) -> None:
        """Start executing state (tool is running)."""
        if tool_calls:
            self._context.tool_calls = tool_calls
        await self.transition_to(SessionState.EXECUTING)

    async def wait_for_user(self) -> None:
        """Transition to waiting for user state."""
        await self.transition_to(SessionState.WAITING_USER)

    async def go_idle(self) -> None:
        """Go to idle state."""
        await self.transition_to(SessionState.IDLE)

    def is_idle(self) -> bool:
        """Check if in IDLE state."""
        return self._state == SessionState.IDLE

    def is_listening(self) -> bool:
        """Check if in LISTENING state."""
        return self._state == SessionState.LISTENING

    def is_thinking(self) -> bool:
        """Check if in THINKING state."""
        return self._state == SessionState.THINKING

    def is_speaking(self) -> bool:
        """Check if in SPEAKING state."""
        return self._state == SessionState.SPEAKING

    def is_executing(self) -> bool:
        """Check if in EXECUTING state."""
        return self._state == SessionState.EXECUTING

    def can_barge_in(self) -> bool:
        """Check if user can barge in at current state."""
        return self._state in {SessionState.SPEAKING, SessionState.THINKING, SessionState.EXECUTING}

    def get_state_description(self) -> str:
        """Get a human-readable description of the current state."""
        descriptions = {
            SessionState.IDLE: "待机中 - 等待用户说话",
            SessionState.LISTENING: "正在听 - 用户说话中",
            SessionState.THINKING: "思考中 - 处理用户输入",
            SessionState.SPEAKING: "说话中 - AI回复播放中",
            SessionState.EXECUTING: "执行中 - 工具运行中",
            SessionState.WAITING_USER: "等待确认 - 需要用户确认",
        }
        return descriptions.get(self._state, "未知状态")
