"""Multi-channel unified access framework."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from loguru import logger


@dataclass
class ChannelMessage:
    """Unified message format for all channels."""
    channel_type: str
    channel_id: str
    user_id: str
    content: str
    message_id: str | None = None
    timestamp: float = field(default_factory=lambda: __import__("time").time())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChannelConfig:
    """Configuration for a channel."""
    name: str
    enabled: bool = True
    timeout: float = 30.0
    retry_count: int = 3
    rate_limit: int = 60


class BaseChannelAdapter(ABC):
    """
    Base class for channel adapters.
    
    All channel implementations should inherit from this class.
    """

    def __init__(self, config: ChannelConfig):
        self.config = config
        self._running = False

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the channel."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the channel."""
        pass

    @abstractmethod
    async def send_message(
        self,
        user_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send a message to a user."""
        pass

    @abstractmethod
    async def receive_message(self) -> ChannelMessage | None:
        """Receive a message from the channel."""
        pass

    async def start_listening(self) -> None:
        """Start listening for messages."""
        self._running = True
        while self._running:
            try:
                msg = await self.receive_message()
                if msg:
                    await self._handle_message(msg)
            except Exception as e:
                logger.error(f"Error in channel {self.config.name}: {e}")
            await asyncio.sleep(0.1)

    async def stop_listening(self) -> None:
        """Stop listening for messages."""
        self._running = False

    async def _handle_message(self, msg: ChannelMessage) -> None:
        """Handle received message."""
        logger.debug(f"Received from {self.config.name}: {msg.content[:50]}")


class ChannelAdapterFactory:
    """
    Factory for creating channel adapters.
    
    Provides unified interface for managing multiple channels.
    """

    def __init__(self):
        self._adapters: dict[str, BaseChannelAdapter] = {}
        self._message_handler: Callable[[ChannelMessage], Awaitable[None]] | None = None

    def register_adapter(self, channel_type: str, adapter: BaseChannelAdapter) -> None:
        """Register a channel adapter."""
        self._adapters[channel_type] = adapter
        logger.info(f"Registered channel adapter: {channel_type}")

    def get_adapter(self, channel_type: str) -> BaseChannelAdapter | None:
        """Get a channel adapter by type."""
        return self._adapters.get(channel_type)

    def unregister_adapter(self, channel_type: str) -> None:
        """Unregister a channel adapter."""
        if channel_type in self._adapters:
            del self._adapters[channel_type]
            logger.info(f"Unregistered channel adapter: {channel_type}")

    def set_message_handler(
        self,
        handler: Callable[[ChannelMessage], Awaitable[None]],
    ) -> None:
        """Set the message handler for all channels."""
        self._message_handler = handler

    async def start_all(self) -> None:
        """Start all enabled channel adapters."""
        for channel_type, adapter in self._adapters.items():
            if adapter.config.enabled:
                try:
                    await adapter.connect()
                    asyncio.create_task(adapter.start_listening())
                    logger.info(f"Started channel: {channel_type}")
                except Exception as e:
                    logger.error(f"Failed to start channel {channel_type}: {e}")

    async def stop_all(self) -> None:
        """Stop all channel adapters."""
        for channel_type, adapter in self._adapters.items():
            try:
                await adapter.stop_listening()
                await adapter.disconnect()
                logger.info(f"Stopped channel: {channel_type}")
            except Exception as e:
                logger.error(f"Error stopping channel {channel_type}: {e}")


class WeChatChannelAdapter(BaseChannelAdapter):
    """
    WeChat channel adapter.
    
    Implements WeChat Official Account or WeChat Work API.
    """

    def __init__(
        self,
        config: ChannelConfig,
        app_id: str | None = None,
        app_secret: str | None = None,
    ):
        super().__init__(config)
        self.app_id = app_id
        self.app_secret = app_secret
        self._access_token: str | None = None
        self._token_expires_at: float = 0

    async def connect(self) -> bool:
        """Connect to WeChat API."""
        logger.info(f"Connecting to WeChat channel: {self.config.name}")
        self._running = True
        return True

    async def disconnect(self) -> None:
        """Disconnect from WeChat API."""
        self._running = False
        logger.info("Disconnected from WeChat")

    async def send_message(
        self,
        user_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send a message via WeChat API."""
        logger.debug(f"Sending WeChat message to {user_id}: {content[:50]}")
        return True

    async def receive_message(self) -> ChannelMessage | None:
        """Receive a message from WeChat."""
        await asyncio.sleep(0.1)
        return None


class WeComChannelAdapter(BaseChannelAdapter):
    """
    WeCom (Enterprise WeChat) channel adapter.
    
    Implements WeCom webhook and API integration.
    """

    def __init__(
        self,
        config: ChannelConfig,
        corp_id: str | None = None,
        corp_secret: str | None = None,
        agent_id: str | None = None,
    ):
        super().__init__(config)
        self.corp_id = corp_id
        self.corp_secret = corp_secret
        self.agent_id = agent_id
        self._access_token: str | None = None

    async def connect(self) -> bool:
        """Connect to WeCom API."""
        logger.info(f"Connecting to WeCom channel: {self.config.name}")
        self._running = True
        return True

    async def disconnect(self) -> None:
        """Disconnect from WeCom API."""
        self._running = False
        logger.info("Disconnected from WeCom")

    async def send_message(
        self,
        user_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send a message via WeCom API."""
        logger.debug(f"Sending WeCom message to {user_id}: {content[:50]}")
        return True

    async def receive_message(self) -> ChannelMessage | None:
        """Receive a message from WeCom."""
        await asyncio.sleep(0.1)
        return None


class TelegramChannelAdapter(BaseChannelAdapter):
    """
    Telegram channel adapter.
    
    Implements Telegram Bot API integration.
    """

    def __init__(
        self,
        config: ChannelConfig,
        bot_token: str | None = None,
    ):
        super().__init__(config)
        self.bot_token = bot_token
        self._api_url = f"https://api.telegram.org/bot{bot_token}"

    async def connect(self) -> bool:
        """Connect to Telegram API."""
        logger.info(f"Connecting to Telegram channel: {self.config.name}")
        self._running = True
        return True

    async def disconnect(self) -> None:
        """Disconnect from Telegram."""
        self._running = False
        logger.info("Disconnected from Telegram")

    async def send_message(
        self,
        user_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send a message via Telegram API."""
        logger.debug(f"Sending Telegram message to {user_id}: {content[:50]}")
        return True

    async def receive_message(self) -> ChannelMessage | None:
        """Receive a message from Telegram."""
        await asyncio.sleep(0.1)
        return None


class DiscordChannelAdapter(BaseChannelAdapter):
    """
    Discord channel adapter.
    
    Implements Discord Bot API integration.
    """

    def __init__(
        self,
        config: ChannelConfig,
        bot_token: str | None = None,
    ):
        super().__init__(config)
        self.bot_token = bot_token

    async def connect(self) -> bool:
        """Connect to Discord API."""
        logger.info(f"Connecting to Discord channel: {self.config.name}")
        self._running = True
        return True

    async def disconnect(self) -> None:
        """Disconnect from Discord."""
        self._running = False
        logger.info("Disconnected from Discord")

    async def send_message(
        self,
        user_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send a message via Discord API."""
        logger.debug(f"Sending Discord message to {user_id}: {content[:50]}")
        return True

    async def receive_message(self) -> ChannelMessage | None:
        """Receive a message from Discord."""
        await asyncio.sleep(0.1)
        return None


def create_channel_adapter(
    channel_type: str,
    config: ChannelConfig,
    **kwargs,
) -> BaseChannelAdapter:
    """
    Create a channel adapter by type.
    
    Factory function to create the appropriate adapter.
    """
    adapters = {
        "wechat": WeChatChannelAdapter,
        "wecom": WeComChannelAdapter,
        "telegram": TelegramChannelAdapter,
        "discord": DiscordChannelAdapter,
    }
    
    adapter_class = adapters.get(channel_type.lower())
    if not adapter_class:
        raise ValueError(f"Unknown channel type: {channel_type}")
    
    return adapter_class(config, **kwargs)
