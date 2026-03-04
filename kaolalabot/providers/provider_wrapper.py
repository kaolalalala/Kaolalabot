"""Provider wrapper with fallback support."""

import asyncio
import time
from typing import Any

from loguru import logger

from kaolalabot.providers.base import LLMProvider, LLMResponse
from kaolalabot.providers.fallback import (
    ProviderFallbackManager,
    ProviderHealthChecker,
    ProviderStatus,
)
from kaolalabot.providers.litellm_provider import LiteLLMProvider


class FallbackEnabledProvider(LLMProvider):
    """
    LLM Provider with automatic fallback support.
    
    Wraps multiple providers and automatically switches to backup providers
    when the primary provider fails.
    """

    def __init__(
        self,
        providers: list[tuple[str, LiteLLMProvider]],
        config: Any | None = None,
    ):
        self.config = config
        self._health_checker = ProviderHealthChecker(
            failure_threshold=getattr(config, 'failure_threshold', 3) if config else 3,
            check_interval=getattr(config, 'health_check_interval', 30.0) if config else 30.0,
        )
        self._fallback_manager = ProviderFallbackManager(
            providers=providers,
            health_checker=self._health_checker,
            failover_timeout=getattr(config, 'failover_timeout', 10.0) if config else 10.0,
            enable_auto_failover=getattr(config, 'enable_fallback', True) if config else True,
        )
        self._default_model = providers[0][1].default_model if providers else "anthropic/claude-sonnet-4-5"

    @property
    def default_model(self) -> str:
        """Get default model from primary provider."""
        return self._default_model

    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
    ) -> LLMResponse:
        """Send a chat completion request with automatic fallback."""
        start_time = time.time()

        async def _call(provider: LiteLLMProvider, msgs: list, tls: list | None, mdl: str | None) -> LLMResponse:
            return await provider.chat(
                messages=msgs,
                tools=tls,
                model=mdl or self.default_model,
                max_tokens=max_tokens,
                temperature=temperature,
                reasoning_effort=reasoning_effort,
            )

        try:
            result = await self._fallback_manager.call_with_fallback(
                _call,
                messages, tools, model
            )
            response_time = time.time() - start_time
            provider_name = self._fallback_manager.current_provider_name
            await self._health_checker.record_success(provider_name, response_time)
            return result

        except Exception as e:
            logger.error(f"All providers failed: {e}")
            return LLMResponse(
                content=f"Error: All LLM providers failed. Last error: {str(e)}",
                finish_reason="error",
            )

    def get_provider_status(self) -> dict[str, Any]:
        """Get status of all providers."""
        return self._fallback_manager.get_provider_status()

    async def switch_provider(self, provider_name: str) -> bool:
        """Manually switch to a specific provider."""
        return await self._fallback_manager.switch_to_provider(provider_name)


def create_fallback_provider(
    config: Any,
    workspace_path: str | None = None,
) -> FallbackEnabledProvider | LiteLLMProvider:
    """
    Create a provider with fallback support based on configuration.
    
    Args:
        config: Configuration object with providers settings
        workspace_path: Optional workspace path
    
    Returns:
        FallbackEnabledProvider if multiple providers configured, else LiteLLMProvider
    """
    from kaolalabot.providers.registry import PROVIDERS

    available_providers = []

    for spec in PROVIDERS:
        p = getattr(config.providers, spec.name, None)
        if p and p.api_key and p.enabled:
            provider = LiteLLMProvider(
                api_key=p.api_key,
                api_base=p.api_base,
                extra_headers=p.extra_headers,
                provider_name=spec.name,
            )
            available_providers.append((spec.name, provider))
            logger.info(f"Added provider to fallback pool: {spec.name}")

    if len(available_providers) > 1 and config.providers.enable_fallback:
        logger.info(f"Creating fallback provider with {len(available_providers)} providers")
        return FallbackEnabledProvider(
            providers=available_providers,
            config=config.providers,
        )
    elif available_providers:
        logger.info("Using single provider without fallback")
        return available_providers[0][1]
    else:
        logger.warning("No providers available")
        return LiteLLMProvider()
