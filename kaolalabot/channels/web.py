"""Web channel for browser-based chat interface."""

from collections.abc import Awaitable, Callable
from typing import Any
from loguru import logger

from kaolalabot.bus.events import OutboundMessage
from kaolalabot.bus.queue import MessageBus
from kaolalabot.channels.base import BaseChannel


class WebChannel(BaseChannel):
    """Channel for web-based chat interface via WebSocket/Socket.IO."""

    name: str = "web"

    def __init__(self, config: Any, bus: MessageBus):
        super().__init__(config, bus)
        self._connected_sessions: dict[str, dict] = {}
        self._sender: Callable[[OutboundMessage], Awaitable[None]] | None = None

    async def start(self) -> None:
        """Start the web channel."""
        logger.info("Web channel started (Socket.IO integration)")
        self._running = True

    async def stop(self) -> None:
        """Stop the web channel."""
        self._running = False
        self._connected_sessions.clear()
        logger.info("Web channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """
        Send a message to the web client.

        This is called when the agent wants to send a response back.
        The actual WebSocket delivery is handled by the Socket.IO handler.
        """
        if self._sender is None:
            logger.warning("Web channel sender not registered; dropping message")
            return
        await self._sender(msg)

    def set_sender(self, sender: Callable[[OutboundMessage], Awaitable[None]]) -> None:
        """Register the async sender used to push messages to socket clients."""
        self._sender = sender

    async def register_session(self, session_id: str, socket_id: str) -> None:
        """Register a connected web session."""
        self._connected_sessions[session_id] = {
            "socket_id": socket_id,
            "connected": True
        }
        logger.info(f"Web session registered: {session_id}")

    async def unregister_session(self, session_id: str) -> None:
        """Unregister a web session."""
        if session_id in self._connected_sessions:
            del self._connected_sessions[session_id]
            logger.info(f"Web session unregistered: {session_id}")

    def get_session(self, session_id: str) -> dict | None:
        """Get session info."""
        return self._connected_sessions.get(session_id)

    @property
    def active_sessions(self) -> int:
        """Get number of active sessions."""
        return len(self._connected_sessions)
