"""MCP bridge service for Minecraft-style command/event transport."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from loguru import logger

EventHandler = Callable[[dict[str, Any]], Awaitable[None] | None]


@dataclass
class MCPPacket:
    """MCP packet representation."""

    packet_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None

    def to_bytes(self) -> bytes:
        body = {
            "type": self.packet_type,
            "payload": self.payload,
            "request_id": self.request_id,
        }
        return (json.dumps(body, ensure_ascii=False) + "\n").encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "MCPPacket":
        raw = json.loads(data.decode("utf-8").strip())
        return cls(
            packet_type=str(raw.get("type", "")),
            payload=raw.get("payload") or {},
            request_id=raw.get("request_id"),
        )


class MCPService:
    """
    MCP service with packet parsing, event listening and command execution.

    Protocol:
    - Newline-delimited JSON packets.
    - Command request: {"type":"command", "request_id":"...", "payload":{"command":"..."}}
    - Command response: {"type":"command_result", "request_id":"...", "payload":{"ok":true,"result":"..."}}
    - Event push: {"type":"event", "payload":{"event":"player_join", ...}}
    """

    def __init__(
        self,
        host: str,
        port: int,
        reconnect_interval_seconds: int = 5,
        command_timeout_seconds: int = 10,
    ):
        self.host = host
        self.port = port
        self.reconnect_interval_seconds = max(1, reconnect_interval_seconds)
        self.command_timeout_seconds = max(1, command_timeout_seconds)

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._running = False
        self._reader_task: asyncio.Task | None = None
        self._connector_task: asyncio.Task | None = None
        self._listeners: dict[str, list[EventHandler]] = defaultdict(list)
        self._pending_commands: dict[str, asyncio.Future] = {}
        self._last_error: str | None = None

    async def start(self) -> None:
        self._running = True
        self._connector_task = asyncio.create_task(self._connect_loop())

    async def stop(self) -> None:
        self._running = False
        if self._connector_task:
            self._connector_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._connector_task
        if self._reader_task:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
        await self._disconnect()

    def on(self, event_name: str, handler: EventHandler) -> None:
        """Register event listener."""
        self._listeners[event_name].append(handler)

    async def execute_command(self, command: str) -> dict[str, Any]:
        """Send command packet and wait for result."""
        if not command.strip():
            return {"ok": False, "error": "empty command"}
        if not self.is_connected:
            return {"ok": False, "error": "mcp not connected"}

        request_id = str(uuid.uuid4())
        packet = MCPPacket(
            packet_type="command",
            request_id=request_id,
            payload={"command": command},
        )
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending_commands[request_id] = fut
        await self._send_packet(packet)
        try:
            return await asyncio.wait_for(fut, timeout=self.command_timeout_seconds)
        except asyncio.TimeoutError:
            return {"ok": False, "error": "command timeout"}
        finally:
            self._pending_commands.pop(request_id, None)

    async def emit_event(self, event_name: str, payload: dict[str, Any] | None = None) -> None:
        """Emit event packet to remote side."""
        await self._send_packet(
            MCPPacket(packet_type="event", payload={"event": event_name, **(payload or {})})
        )

    @property
    def is_connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    def status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "connected": self.is_connected,
            "host": self.host,
            "port": self.port,
            "pending_commands": len(self._pending_commands),
            "last_error": self._last_error,
        }

    async def _connect_loop(self) -> None:
        while self._running:
            if self.is_connected:
                await asyncio.sleep(1)
                continue
            try:
                self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
                self._last_error = None
                logger.info("MCP connected to {}:{}", self.host, self.port)
                self._reader_task = asyncio.create_task(self._read_loop())
            except Exception as exc:
                self._last_error = str(exc)
                logger.warning("MCP connect failed: {}", exc)
                await asyncio.sleep(self.reconnect_interval_seconds)

    async def _disconnect(self) -> None:
        if self._writer:
            self._writer.close()
            with contextlib.suppress(Exception):
                await self._writer.wait_closed()
        self._reader = None
        self._writer = None

    async def _send_packet(self, packet: MCPPacket) -> None:
        if not self.is_connected:
            raise RuntimeError("MCP not connected")
        assert self._writer is not None
        self._writer.write(packet.to_bytes())
        await self._writer.drain()

    async def _read_loop(self) -> None:
        try:
            assert self._reader is not None
            while self._running and self._reader:
                line = await self._reader.readline()
                if not line:
                    break
                try:
                    packet = MCPPacket.from_bytes(line)
                except Exception as exc:
                    logger.warning("MCP packet parse error: {}", exc)
                    continue
                await self._handle_packet(packet)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._last_error = str(exc)
            logger.warning("MCP read loop error: {}", exc)
        finally:
            await self._disconnect()

    async def _handle_packet(self, packet: MCPPacket) -> None:
        if packet.packet_type == "command_result" and packet.request_id:
            fut = self._pending_commands.get(packet.request_id)
            if fut and not fut.done():
                fut.set_result(packet.payload)
            return

        if packet.packet_type == "event":
            event_name = str(packet.payload.get("event", ""))
            if event_name:
                await self._dispatch_event(event_name, packet.payload)
            return

        await self._dispatch_event(packet.packet_type, packet.payload)

    async def _dispatch_event(self, event_name: str, payload: dict[str, Any]) -> None:
        listeners = self._listeners.get(event_name, [])
        for handler in listeners:
            try:
                result = handler(payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.warning("MCP event handler error on {}: {}", event_name, exc)


import contextlib

