"""Agent Bridge interface for connecting voice to kaolalabot agent."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Awaitable, Callable


@dataclass
class AgentToken:
    """Represents a single token from the agent."""

    text: str
    is_final: bool
    tool_call_id: str | None = None
    tool_name: str | None = None


class AgentBridge(ABC):
    """Abstract base class for agent bridges."""

    @abstractmethod
    async def run(
        self,
        query: str,
        session_key: str = "voice:session",
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> AsyncIterator[AgentToken]:
        """
        Run the agent with a query and yield streaming tokens.

        Args:
            query: User query text
            session_key: Session identifier
            on_progress: Optional callback for progress updates

        Yields:
            AgentToken objects with streaming response
        """
        pass

    @abstractmethod
    async def cancel(self) -> None:
        """Cancel the current agent operation."""
        pass

    @abstractmethod
    async def start(self) -> None:
        """Start the agent bridge."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the agent bridge."""
        pass
