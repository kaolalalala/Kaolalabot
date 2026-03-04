"""OpenClaw Bridge - connects voice to kaolalabot's existing AgentLoop."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Awaitable, Callable

from loguru import logger

from .agent_interface import AgentBridge, AgentToken


class OpenClawBridge(AgentBridge):
    """
    Bridge connecting voice interaction to kaolalabot's AgentLoop.

    This bridge:
    - Wraps the existing AgentLoop from kaolalabot
    - Provides streaming token output for TTS
    - Supports cancellation for barge-in
    - Manages session state for voice conversations
    """

    def __init__(
        self,
        agent_loop,
        session_key: str = "voice:session",
    ):
        """
        Initialize the bridge.

        Args:
            agent_loop: The kaolalabot AgentLoop instance
            session_key: Default session key for voice conversations
        """
        self._agent_loop = agent_loop
        self._default_session_key = session_key
        self._running = False
        self._current_task: asyncio.Task | None = None
        self._cancelled = False

    async def start(self) -> None:
        """Start the agent bridge."""
        self._running = True

    async def stop(self) -> None:
        """Stop the agent bridge."""
        self._running = False
        await self.cancel()

    async def run(
        self,
        query: str,
        session_key: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> AsyncIterator[AgentToken]:
        """
        Run the agent with query and yield streaming tokens.

        This method:
        1. Calls the AgentLoop to process the query
        2. Captures streaming progress (if available)
        3. Yields tokens for TTS synthesis

        Args:
            query: User query text
            session_key: Session identifier (uses default if not provided)
            on_progress: Callback for progress updates

        Yields:
            AgentToken objects with response text
        """
        if not self._running:
            await self.start()

        self._cancelled = False
        key = session_key or self._default_session_key

        token_buffer = ""

        try:
            if hasattr(self._agent_loop, "process_direct"):
                progress_calls = []

                async def progress_handler(content: str) -> None:
                    nonlocal token_buffer
                    if self._cancelled:
                        return
                    if content:
                        token_buffer += content + " "
                        progress_calls.append(content)
                        if on_progress:
                            await on_progress(content)

                result = await self._agent_loop.process_direct(
                    content=query,
                    session_key=key,
                    channel="voice",
                    chat_id=key,
                    on_progress=progress_handler,
                )

                if not self._cancelled and result:
                    token_buffer = result
                    yield AgentToken(
                        text=result,
                        is_final=True,
                    )
                elif progress_calls:
                    for pc in progress_calls:
                        yield AgentToken(text=pc, is_final=False)
            else:
                logger.warning("AgentLoop does not support process_direct method")
                yield AgentToken(
                    text="抱歉，语音服务暂时不可用。",
                    is_final=True,
                )

        except asyncio.CancelledError:
            self._cancelled = True
            logger.info("Agent execution cancelled")
            raise
        except Exception as e:
            logger.error("Agent execution error: {}", e)
            yield AgentToken(
                text="抱歉，处理您的请求时发生错误。",
                is_final=True,
            )

    async def cancel(self) -> None:
        """Cancel the current agent operation."""
        self._cancelled = True

        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass

    @property
    def is_running(self) -> bool:
        """Check if bridge is running."""
        return self._running


class DirectProviderBridge(AgentBridge):
    """
    Direct bridge using LLM provider without full AgentLoop.

    Use this when you want simpler voice interaction without
    the full tool execution capabilities.
    """

    def __init__(
        self,
        provider,
        model: str = "gpt-4o-mini",
        system_prompt: str | None = None,
    ):
        """
        Initialize the bridge.

        Args:
            provider: LLM provider instance
            model: Model name to use
            system_prompt: Optional system prompt
        """
        self._provider = provider
        self._model = model
        self._system_prompt = system_prompt or "你是一个友好的AI助手。请用简洁的中文回答。"

        self._running = False
        self._cancelled = False

    async def start(self) -> None:
        """Start the bridge."""
        self._running = True

    async def stop(self) -> None:
        """Stop the bridge."""
        self._running = False

    async def run(
        self,
        query: str,
        session_key: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> AsyncIterator[AgentToken]:
        """Run the provider with query and yield streaming response."""
        if not self._running:
            await self.start()

        self._cancelled = False

        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": query},
        ]

        try:
            response = await self._provider.chat(
                messages=messages,
                model=self._model,
                temperature=0.7,
                max_tokens=1024,
            )

            if self._cancelled:
                return

            content = response.content or ""

            if content:
                if on_progress:
                    await on_progress(content)

                yield AgentToken(
                    text=content,
                    is_final=True,
                )

        except asyncio.CancelledError:
            self._cancelled = True
            raise
        except Exception as e:
            logger.error("Provider error: {}", e)
            yield AgentToken(
                text="抱歉，发生了一些错误。",
                is_final=True,
            )

    async def cancel(self) -> None:
        """Cancel current operation."""
        self._cancelled = True
