"""DingTalk channel implementation."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import hmac
import time
import urllib.parse
from typing import Any

from loguru import logger

from kaolalabot.bus.events import OutboundMessage
from kaolalabot.bus.queue import MessageBus
from kaolalabot.channels.base import BaseChannel
from kaolalabot.config.schema import DingTalkConfig

try:
    import aiohttp
    from aiohttp import web

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


class DingTalkChannel(BaseChannel):
    """DingTalk channel via callback + robot webhook send."""

    name = "dingtalk"

    def __init__(self, config: DingTalkConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config = config
        self._session: aiohttp.ClientSession | None = None
        self._health_task: asyncio.Task | None = None
        self._web_runner: web.AppRunner | None = None
        self._last_error: str | None = None
        self._connected: bool = False

    async def start(self) -> None:
        if not AIOHTTP_AVAILABLE:
            logger.error("DingTalk channel requires aiohttp: pip install aiohttp")
            return
        self._running = True
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15)
        )
        await self._start_callback_server()
        self._health_task = asyncio.create_task(self._health_loop())
        self._connected = True
        logger.info("DingTalk channel started")

    async def stop(self) -> None:
        self._running = False
        if self._health_task:
            self._health_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._health_task
        if self._web_runner:
            await self._web_runner.cleanup()
            self._web_runner = None
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None
        self._connected = False
        logger.info("DingTalk channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        if not msg.content:
            return
        ok = await self._send_text_with_retry(msg.content)
        if not ok:
            logger.error("Failed to send DingTalk message after retries")

    async def handle_callback(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle inbound DingTalk callback payload."""
        text = self._extract_text(payload)
        sender_id = self._extract_sender(payload)
        chat_id = self._extract_chat_id(payload, sender_id)

        if not text:
            return {"msgtype": "text", "text": {"content": "消息已收到（非文本消息）"}}

        await self._handle_message(
            sender_id=sender_id,
            chat_id=chat_id,
            content=text,
            metadata={"raw": payload},
        )
        return {"msgtype": "text", "text": {"content": "消息已收到，正在处理中。"}}

    def status(self) -> dict[str, Any]:
        """Return current channel status."""
        return {
            "running": self._running,
            "connected": self._connected,
            "last_error": self._last_error,
            "callback_url": f"http://{self.config.callback_host}:{self.config.callback_port}{self.config.callback_path}",
        }

    async def _health_loop(self) -> None:
        """Background health loop with lightweight reconnect."""
        while self._running:
            try:
                if self._session is None or self._session.closed:
                    self._session = aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=15)
                    )
                    self._connected = True
                    logger.info("DingTalk channel session reconnected")
            except Exception as exc:
                self._connected = False
                self._last_error = str(exc)
                logger.warning("DingTalk health loop error: {}", exc)
            await asyncio.sleep(max(3, self.config.health_check_interval_seconds))

    async def _start_callback_server(self) -> None:
        """Start internal HTTP callback listener for DingTalk events."""
        app = web.Application()

        async def _callback_handler(request: web.Request) -> web.Response:
            payload = await request.json()
            data = await self.handle_callback(payload)
            return web.json_response(data)

        async def _status_handler(request: web.Request) -> web.Response:
            return web.json_response(self.status())

        app.router.add_post(self.config.callback_path, _callback_handler)
        app.router.add_get("/dingtalk/status", _status_handler)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(
            runner,
            host=self.config.callback_host,
            port=self.config.callback_port,
        )
        await site.start()
        self._web_runner = runner
        logger.info(
            "DingTalk callback server listening on http://{}:{}{}",
            self.config.callback_host,
            self.config.callback_port,
            self.config.callback_path,
        )

    async def _send_text_with_retry(self, content: str) -> bool:
        if not self._session:
            self._last_error = "Session not initialized"
            return False

        webhook_url = self._build_webhook_url()
        if not webhook_url:
            self._last_error = "DingTalk webhook_access_token not configured"
            logger.warning(self._last_error)
            return False

        payload = {"msgtype": "text", "text": {"content": content}}
        retries = max(0, self.config.max_retries)

        for attempt in range(retries + 1):
            try:
                async with self._session.post(webhook_url, json=payload) as resp:
                    data = await resp.json(content_type=None)
                    if resp.status == 200 and int(data.get("errcode", 1)) == 0:
                        self._connected = True
                        self._last_error = None
                        return True
                    self._connected = False
                    self._last_error = f"HTTP {resp.status}, response={data}"
            except Exception as exc:
                self._connected = False
                self._last_error = str(exc)

            if attempt < retries:
                await asyncio.sleep(max(1, self.config.reconnect_interval_seconds))

        return False

    def _build_webhook_url(self) -> str | None:
        token = (self.config.webhook_access_token or "").strip()
        if not token:
            return None
        base = f"https://oapi.dingtalk.com/robot/send?access_token={urllib.parse.quote(token)}"
        secret = (self.config.webhook_secret or "").strip()
        if not secret:
            return base

        timestamp = str(round(time.time() * 1000))
        sign_payload = f"{timestamp}\n{secret}".encode("utf-8")
        sign = urllib.parse.quote_plus(
            base64.b64encode(
                hmac.new(secret.encode("utf-8"), sign_payload, digestmod=hashlib.sha256).digest()
            )
        )
        return f"{base}&timestamp={timestamp}&sign={sign}"

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        text = payload.get("text")
        if isinstance(text, dict):
            content = text.get("content")
            return str(content).strip() if content else ""
        if isinstance(text, str):
            return text.strip()
        # Event callback format fallback.
        value = payload.get("content") or payload.get("msg")
        return str(value).strip() if value else ""

    @staticmethod
    def _extract_sender(payload: dict[str, Any]) -> str:
        for key in ("senderStaffId", "senderId", "staffId", "userid"):
            value = payload.get(key)
            if value:
                return str(value)
        sender = payload.get("sender")
        if isinstance(sender, dict):
            for key in ("staffId", "id", "userid"):
                value = sender.get(key)
                if value:
                    return str(value)
        return "unknown"

    @staticmethod
    def _extract_chat_id(payload: dict[str, Any], sender_id: str) -> str:
        for key in ("conversationId", "chatbotConversationId", "sessionWebhook"):
            value = payload.get(key)
            if value:
                return str(value)
        return sender_id
