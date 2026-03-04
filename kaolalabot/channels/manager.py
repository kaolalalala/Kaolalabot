"""Channel manager for coordinating chat channels."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from kaolalabot.bus.queue import MessageBus
from kaolalabot.channels.base import BaseChannel
from kaolalabot.config.schema import Config


ChannelFactory = Callable[[], BaseChannel]


class ChannelManager:
    """
    Manages chat channels and coordinates message routing.

    Uses lazy channel factories so heavy SDK imports do not happen during
    manager construction.
    """

    _active_manager: "ChannelManager | None" = None

    def __init__(self, config: Config, bus: MessageBus):
        self.config = config
        self.bus = bus
        self.channels: dict[str, BaseChannel] = {}
        self._channel_factories: dict[str, ChannelFactory] = {}
        self._dispatch_task: asyncio.Task | None = None

        ChannelManager._active_manager = self
        self._init_channel_factories()

    def _init_channel_factories(self) -> None:
        """Register channel factories based on config."""
        if self.config.channels.feishu.enabled:
            self._channel_factories["feishu"] = self._build_feishu_channel
            logger.info("Feishu channel enabled")

        if getattr(self.config, "mcp", None) and getattr(self.config.mcp, "enabled", False):
            self._channel_factories["mcp"] = self._build_mcp_channel
            logger.info("MCP channel enabled")

        dingtalk_config = getattr(self.config.channels, "dingtalk", None)
        if dingtalk_config and getattr(dingtalk_config, "enabled", False):
            self._channel_factories["dingtalk"] = self._build_dingtalk_channel
            logger.info("DingTalk channel enabled")

        self._channel_factories["web"] = self._build_web_channel
        logger.info("Web channel enabled")

        voice_config = getattr(self.config.channels, "voice", None)
        if voice_config and getattr(voice_config, "enabled", False):
            self._channel_factories["voice"] = self._build_voice_channel
            logger.info("Voice channel enabled")

    def _ensure_channel(self, name: str) -> BaseChannel | None:
        channel = self.channels.get(name)
        if channel:
            return channel
        factory = self._channel_factories.get(name)
        if not factory:
            return None
        try:
            channel = factory()
        except Exception as exc:
            logger.error("Failed to initialize channel {}: {}", name, exc)
            return None
        self.channels[name] = channel
        return channel

    def _build_feishu_channel(self) -> BaseChannel:
        from kaolalabot.channels.feishu import FeishuChannel

        return FeishuChannel(self.config.channels.feishu, self.bus)

    def _build_dingtalk_channel(self) -> BaseChannel:
        from kaolalabot.channels.dingtalk import DingTalkChannel

        return DingTalkChannel(self.config.channels.dingtalk, self.bus)

    def _build_mcp_channel(self) -> BaseChannel:
        from kaolalabot.channels.mcp_channel import MCPChannel

        return MCPChannel(self.config.mcp, self.bus)

    def _build_web_channel(self) -> BaseChannel:
        from kaolalabot.channels.web import WebChannel

        web_config = (
            self.config.channels.model_dump()
            if hasattr(self.config.channels, "model_dump")
            else {}
        )
        return WebChannel(web_config, self.bus)

    def _build_voice_channel(self) -> BaseChannel:
        from kaolalabot.agent.loop import AgentLoop
        from kaolalabot.agent.tools import create_default_tools
        from kaolalabot.channels.voice_channel import VoiceChannel
        from kaolalabot.config.loader import load_config
        from kaolalabot.providers.litellm_provider import LiteLLMProvider

        config_loader = load_config()
        provider = LiteLLMProvider(
            api_key=config_loader.get_api_key(),
            api_base=config_loader.get_api_base(),
            default_model=(
                config_loader.agents.defaults.model
                if hasattr(config_loader, "agents")
                else "deepseek/deepseek-coder"
            ),
        )
        workspace = Path("workspace")
        agent_loop = AgentLoop(
            bus=self.bus,
            provider=provider,
            workspace=workspace,
            tool_registry=create_default_tools(
                workspace=workspace,
                config=(
                    config_loader.tools
                    if hasattr(config_loader, "tools")
                    else None
                ),
            ),
            tools_config=config_loader.tools if hasattr(config_loader, "tools") else None,
            rate_limit_config=(
                config_loader.rate_limit
                if hasattr(config_loader, "rate_limit")
                else None
            ),
        )
        voice_cfg = self.config.channels.voice
        return VoiceChannel(
            config=voice_cfg.model_dump() if hasattr(voice_cfg, "model_dump") else {},
            bus=self.bus,
            agent_loop=agent_loop,
        )

    async def _start_channel(self, name: str) -> None:
        channel = self._ensure_channel(name)
        if not channel:
            return
        try:
            await channel.start()
        except Exception as exc:
            logger.error("Failed to start channel {}: {}", name, exc)

    async def start_all(self) -> None:
        """Start all channels and the outbound dispatcher."""
        if not self._channel_factories:
            logger.warning("No channels enabled")
            return

        self._dispatch_task = asyncio.create_task(self._dispatch_outbound())

        tasks: list[asyncio.Task] = []
        for name in list(self._channel_factories.keys()):
            logger.info("Starting {} channel...", name)
            tasks.append(asyncio.create_task(self._start_channel(name)))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop_all(self) -> None:
        """Stop all channels and the dispatcher."""
        logger.info("Stopping all channels...")
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass

        for name, channel in list(self.channels.items()):
            try:
                await channel.stop()
                logger.info("Stopped {} channel", name)
            except Exception as exc:
                logger.error("Error stopping {}: {}", name, exc)

    async def _dispatch_outbound(self) -> None:
        """Dispatch outbound messages to the appropriate channel."""
        logger.info("Outbound dispatcher started")

        while True:
            try:
                msg = await asyncio.wait_for(self.bus.consume_outbound(), timeout=1.0)

                if msg.metadata.get("_progress"):
                    if msg.channel == "feishu" and not msg.metadata.get("_tool_hint"):
                        continue
                    if msg.metadata.get("_tool_hint") and not self.config.channels.send_tool_hints:
                        continue
                    if not msg.metadata.get("_tool_hint") and not self.config.channels.send_progress:
                        continue

                channel = self._ensure_channel(msg.channel)
                if channel:
                    await channel.send(msg)
                else:
                    logger.warning("Unknown channel: {}", msg.channel)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Outbound dispatch error: {}", exc)

    def get_channel(self, name: str) -> BaseChannel | None:
        """Get a channel by name."""
        return self._ensure_channel(name)

    def get_dingtalk_channel(self):
        """Return DingTalk channel if enabled."""
        return self._ensure_channel("dingtalk")

    def get_status(self) -> dict[str, Any]:
        """Get status of all channels."""
        data: dict[str, Any] = {}
        for name in self.enabled_channels:
            channel = self.channels.get(name)
            data[name] = {"enabled": True, "running": bool(channel and channel.is_running)}
        return data

    @property
    def enabled_channels(self) -> list[str]:
        """Get list of enabled channel names."""
        return list(self._channel_factories.keys())

    @classmethod
    def get_active(cls) -> "ChannelManager | None":
        """Return current active manager instance."""
        return cls._active_manager
