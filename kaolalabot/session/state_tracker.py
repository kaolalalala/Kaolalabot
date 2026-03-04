"""Session state tracking and context management system."""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger


class SessionState(Enum):
    """Session state enumeration."""
    ACTIVE = "active"
    IDLE = "idle"
    SUSPENDED = "suspended"
    COMPLETED = "completed"


class ContextType(Enum):
    """Types of context in a session."""
    TASK = "task"
    INFORMATION = "information"
    PREFERENCE = "preference"
    EMOTION = "emotion"
    INTENT = "intent"


@dataclass
class ContextEntry:
    """A single context entry in session state."""
    id: str
    type: ContextType
    content: str
    importance: float = 1.0
    timestamp: float = field(default_factory=time.time)
    expires_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if this context entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


@dataclass
class SessionStateData:
    """Complete state data for a session."""
    session_key: str
    state: SessionState = SessionState.ACTIVE
    current_task: str | None = None
    task_history: list[dict[str, Any]] = field(default_factory=list)
    context_stack: list[ContextEntry] = field(default_factory=list)
    last_activity: float = field(default_factory=time.time)
    message_count: int = 0
    turn_count: int = 0
    user_satisfaction: float | None = None
    pending_responses: list[str] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)


class SessionStateTracker:
    """
    Session state tracker for context management.
    
    Tracks session state, maintains context stack, and manages
    conversation coherence across multiple turns.
    """

    def __init__(
        self,
        max_context_entries: int = 50,
        context_ttl: float = 3600.0,
        inactivity_timeout: float = 1800.0,
    ):
        self.max_context_entries = max_context_entries
        self.context_ttl = context_ttl
        self.inactivity_timeout = inactivity_timeout
        self._sessions: dict[str, SessionStateData] = {}

    def get_or_create_session(self, session_key: str) -> SessionStateData:
        """Get or create a session state."""
        if session_key not in self._sessions:
            self._sessions[session_key] = SessionStateData(session_key=session_key)
            logger.debug(f"Created new session state: {session_key}")
        return self._sessions[session_key]

    def update_activity(self, session_key: str) -> None:
        """Update last activity timestamp for a session."""
        session = self.get_or_create_session(session_key)
        session.last_activity = time.time()
        if session.state == SessionState.IDLE:
            session.state = SessionState.ACTIVE

    def record_message(self, session_key: str, role: str, content: str) -> None:
        """Record a message in the session."""
        session = self.get_or_create_session(session_key)
        session.message_count += 1
        session.last_activity = time.time()
        
        if role == "user":
            session.turn_count += 1

    def set_current_task(self, session_key: str, task: str) -> None:
        """Set the current task for a session."""
        session = self.get_or_create_session(session_key)
        session.current_task = task
        session.state = SessionState.ACTIVE
        logger.debug(f"Session {session_key} task: {task}")

    def add_context(
        self,
        session_key: str,
        context_type: ContextType,
        content: str,
        importance: float = 1.0,
        ttl: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add a context entry to the session."""
        session = self.get_or_create_session(session_key)
        
        entry = ContextEntry(
            id=f"{session_key}:{len(session.context_stack)}",
            type=context_type,
            content=content,
            importance=importance,
            expires_at=time.time() + ttl if ttl else time.time() + self.context_ttl,
            metadata=metadata or {},
        )
        
        session.context_stack.append(entry)
        self._cleanup_expired_contexts(session)
        
        if len(session.context_stack) > self.max_context_entries:
            self._prune_low_importance(session)
        
        return entry.id

    def get_relevant_context(
        self,
        session_key: str,
        context_types: list[ContextType] | None = None,
        max_entries: int = 10,
    ) -> list[ContextEntry]:
        """Get relevant context entries for the session."""
        session = self.get_or_create_session(session_key)
        self._cleanup_expired_contexts(session)
        
        contexts = session.context_stack
        
        if context_types:
            contexts = [c for c in contexts if c.type in context_types]
        
        contexts = sorted(contexts, key=lambda x: (x.importance, x.timestamp), reverse=True)
        return contexts[:max_entries]

    def get_context_summary(self, session_key: str) -> str:
        """Get a summary of session context."""
        session = self.get_or_create_session(session_key)
        
        parts = []
        
        if session.current_task:
            parts.append(f"当前任务: {session.current_task}")
        
        if session.turn_count > 0:
            parts.append(f"对话轮次: {session.turn_count}")
        
        context_by_type: dict[ContextType, int] = {}
        for ctx in session.context_stack:
            context_by_type[ctx.type] = context_by_type.get(ctx.type, 0) + 1
        
        if context_by_type:
            type_summary = ", ".join(f"{t.value}: {c}" for t, c in context_by_type.items())
            parts.append(f"上下文: {type_summary}")
        
        return " | ".join(parts) if parts else "无上下文"

    def _cleanup_expired_contexts(self, session: SessionStateData) -> None:
        """Remove expired context entries."""
        session.context_stack = [
            c for c in session.context_stack if not c.is_expired()
        ]

    def _prune_low_importance(self, session: SessionStateData) -> None:
        """Prune lowest importance contexts when limit exceeded."""
        if len(session.context_stack) <= self.max_context_entries:
            return
        
        sorted_contexts = sorted(
            session.context_stack,
            key=lambda x: (x.importance, x.timestamp),
        )
        
        to_remove = len(session.context_stack) - self.max_context_entries
        removed_ids = {c.id for c in sorted_contexts[:to_remove]}
        
        session.context_stack = [
            c for c in session.context_stack if c.id not in removed_ids
        ]

    def add_task_to_history(
        self,
        session_key: str,
        task: str,
        result: str | None = None,
        success: bool = True,
    ) -> None:
        """Add completed task to history."""
        session = self.get_or_create_session(session_key)
        
        session.task_history.append({
            "task": task,
            "result": result,
            "success": success,
            "timestamp": datetime.now().isoformat(),
        })
        
        if len(session.task_history) > 50:
            session.task_history = session.task_history[-50:]

    def set_idle(self, session_key: str) -> None:
        """Mark session as idle."""
        session = self.get_or_create_session(session_key)
        session.state = SessionState.IDLE

    def is_inactive(self, session_key: str) -> bool:
        """Check if session is inactive."""
        session = self._sessions.get(session_key)
        if not session:
            return True
        
        return (time.time() - session.last_activity) > self.inactivity_timeout

    def get_session_info(self, session_key: str) -> dict[str, Any]:
        """Get complete session information."""
        session = self.get_or_create_session(session_key)
        
        return {
            "session_key": session.session_key,
            "state": session.state.value,
            "current_task": session.current_task,
            "message_count": session.message_count,
            "turn_count": session.turn_count,
            "last_activity": datetime.fromtimestamp(session.last_activity).isoformat(),
            "context_count": len(session.context_stack),
            "task_history_count": len(session.task_history),
        }


class ContextualResponseBuilder:
    """
    Builds contextual responses based on session state.
    
    Uses session context to generate more coherent and contextually
    relevant responses.
    """

    def __init__(self, state_tracker: SessionStateTracker):
        self.state_tracker = state_tracker

    def build_context_prompt(
        self,
        session_key: str,
        include_task: bool = True,
        include_preferences: bool = True,
    ) -> str:
        """Build a context prompt for LLM."""
        parts = []
        
        if include_task:
            session = self.state_tracker.get_or_create_session(session_key)
            if session.current_task:
                parts.append(f"当前任务: {session.current_task}")
        
        if include_preferences:
            prefs = self.state_tracker.get_relevant_context(
                session_key,
                context_types=[ContextType.PREFERENCE],
                max_entries=5,
            )
            if prefs:
                pref_text = "; ".join(f"{p.content}" for p in prefs)
                parts.append(f"用户偏好: {pref_text}")
        
        if parts:
            return "上下文信息: " + " | ".join(parts)
        return ""

    def should_offer_help(self, session_key: str) -> bool:
        """Determine if the system should offer proactive help."""
        session = self.state_tracker.get_or_create_session(session_key)
        
        if session.state == SessionState.IDLE:
            return True
        
        recent_intents = self.state_tracker.get_relevant_context(
            session_key,
            context_types=[ContextType.INTENT],
            max_entries=3,
        )
        
        if len(recent_intents) < 2:
            return False
        
        return False
