"""MCP channel backed by MCPService for Minecraft communication."""

from __future__ import annotations

from typing import Any

from loguru import logger

from kaolalabot.bus.events import OutboundMessage
from kaolalabot.bus.queue import MessageBus
from kaolalabot.channels.base import BaseChannel
from kaolalabot.config.schema import MCPConfig
from kaolalabot.services.mcp import MCPService


class MCPChannel(BaseChannel):
    """Channel that maps MCP chat events to inbound messages and responses back."""

    name = "mcp"

    def __init__(self, config: MCPConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config = config
        self._service = MCPService(
            host=config.host,
            port=config.port,
            reconnect_interval_seconds=config.reconnect_interval_seconds,
            command_timeout_seconds=config.command_timeout_seconds,
        )
        self._service.on("chat_message", self._on_chat_message)

    async def start(self) -> None:
        self._running = True
        await self._service.start()
        logger.info("MCP channel started")

    async def stop(self) -> None:
        self._running = False
        await self._service.stop()
        logger.info("MCP channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        if not msg.content.strip():
            return
        # Default strategy: use "say ..." to broadcast response.
        command = msg.metadata.get("mcp_command")
        if not command:
            safe = msg.content.replace("\n", " ").strip()
            command = f"say {safe}"
        result = await self._service.execute_command(str(command))
        if not result.get("ok"):
            logger.warning("MCP outbound command failed: {}", result.get("error"))

    async def _on_chat_message(self, payload: dict[str, Any]) -> None:
        content = str(payload.get("content") or payload.get("message") or "")
        sender = str(payload.get("player") or payload.get("sender") or "minecraft")
        chat_id = str(payload.get("world") or "minecraft")
        if not content:
            return
        await self._handle_message(
            sender_id=sender,
            chat_id=chat_id,
            content=content,
            metadata={"mcp_event": payload},
        )

    @property
    def service(self) -> MCPService:
        return self._service

