"""Multi-provider fallback and health management system."""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


class ProviderStatus(Enum):
    """Provider health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ProviderHealth:
    """Health information for a provider."""
    name: str
    status: ProviderStatus = ProviderStatus.UNKNOWN
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_check_time: float = 0.0
    last_success_time: float = 0.0
    last_failure_time: float = 0.0
    avg_response_time: float = 0.0
    total_requests: int = 0
    failed_requests: int = 0


class ProviderHealthChecker:
    """
    Health checker for LLM providers.
    
    Monitors provider health and tracks metrics for failover decisions.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        success_threshold: int = 2,
        check_interval: float = 30.0,
        response_time_threshold: float = 30.0,
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.check_interval = check_interval
        self.response_time_threshold = response_time_threshold
        self._health_data: dict[str, ProviderHealth] = {}
        self._lock = asyncio.Lock()

    async def record_success(self, provider_name: str, response_time: float) -> None:
        """Record a successful request."""
        async with self._lock:
            health = self._get_or_create(provider_name)
            health.consecutive_successes += 1
            health.consecutive_failures = 0
            health.last_success_time = time.time()
            health.total_requests += 1
            health.last_check_time = time.time()

            if health.avg_response_time == 0:
                health.avg_response_time = response_time
            else:
                health.avg_response_time = (health.avg_response_time * 0.9) + (response_time * 0.1)

            if health.consecutive_successes >= self.success_threshold:
                health.status = ProviderStatus.HEALTHY
                logger.info(f"Provider {provider_name} recovered to HEALTHY")

    async def record_failure(self, provider_name: str) -> None:
        """Record a failed request."""
        async with self._lock:
            health = self._get_or_create(provider_name)
            health.consecutive_failures += 1
            health.consecutive_successes = 0
            health.last_failure_time = time.time()
            health.total_requests += 1
            health.failed_requests += 1
            health.last_check_time = time.time()

            if health.consecutive_failures >= self.failure_threshold:
                health.status = ProviderStatus.UNHEALTHY
                logger.warning(f"Provider {provider_name} marked as UNHEALTHY after {health.consecutive_failures} failures")
            elif health.status != ProviderStatus.UNHEALTHY:
                health.status = ProviderStatus.DEGRADED
                logger.info(f"Provider {provider_name} degraded after {health.consecutive_failures} failures")

    def _get_or_create(self, provider_name: str) -> ProviderHealth:
        """Get or create health data for a provider."""
        if provider_name not in self._health_data:
            self._health_data[provider_name] = ProviderHealth(name=provider_name)
        return self._health_data[provider_name]

    def get_status(self, provider_name: str) -> ProviderStatus:
        """Get current status of a provider."""
        health = self._health_data.get(provider_name)
        return health.status if health else ProviderStatus.UNKNOWN

    def is_available(self, provider_name: str) -> bool:
        """Check if a provider is available for requests."""
        status = self.get_status(provider_name)
        return status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)

    def get_health_data(self, provider_name: str) -> ProviderHealth | None:
        """Get full health data for a provider."""
        return self._health_data.get(provider_name)

    def get_all_health_data(self) -> dict[str, ProviderHealth]:
        """Get health data for all providers."""
        return self._health_data.copy()


class ProviderFallbackManager:
    """
    Manages provider failover with automatic switching.
    
    Implements health checking, fault detection, and automatic failover
    to improve system availability to 99%.
    """

    def __init__(
        self,
        providers: list[tuple[str, Any]],
        health_checker: ProviderHealthChecker | None = None,
        failover_timeout: float = 10.0,
        enable_auto_failover: bool = True,
    ):
        self.providers = providers
        self.health_checker = health_checker or ProviderHealthChecker()
        self.failover_timeout = failover_timeout
        self.enable_auto_failover = enable_auto_failover
        self._current_provider_index = 0
        self._lock = asyncio.Lock()
        self._last_failover_time = 0.0

    @property
    def current_provider(self) -> tuple[str, Any]:
        """Get the current active provider."""
        if not self.providers:
            raise ValueError("No providers configured")
        return self.providers[self._current_provider_index]

    @property
    def current_provider_name(self) -> str:
        """Get the name of the current provider."""
        return self.current_provider[0]

    async def get_available_provider(self) -> tuple[str, Any] | None:
        """Get an available provider, considering health status."""
        async with self._lock:
            for i, (name, provider) in enumerate(self.providers):
                if self.health_checker.is_available(name):
                    if i != self._current_provider_index:
                        self._current_provider_index = i
                        logger.info(f"Switching to provider: {name}")
                    return (name, provider)
            return None

    async def call_with_fallback(
        self,
        func: Any,
        *args,
        **kwargs,
    ) -> Any:
        """
        Call a function with automatic provider fallback.
        
        If the current provider fails, automatically switches to the next
        available provider.
        """
        if not self.enable_auto_failover:
            return await func(*args, **kwargs)

        start_time = time.time()
        last_error = None

        for attempt in range(len(self.providers)):
            provider_name, provider = await self.get_available_provider()
            if provider is None:
                logger.error("No available providers")
                raise RuntimeError("No available providers")

            try:
                logger.debug(f"Attempting request with provider: {provider_name}")
                result = await func(provider, *args, **kwargs)

                response_time = time.time() - start_time
                await self.health_checker.record_success(provider_name, response_time)
                return result

            except Exception as e:
                last_error = e
                logger.warning(f"Provider {provider_name} failed: {e}")
                await self.health_checker.record_failure(provider_name)

                async with self._lock:
                    self._current_provider_index = (self._current_provider_index + 1) % len(self.providers)
                    self._last_failover_time = time.time()

                if attempt < len(self.providers) - 1:
                    logger.info(f"Failing over to next provider...")
                    await asyncio.sleep(0.5)

        raise last_error or RuntimeError("All providers failed")

    async def switch_to_provider(self, provider_name: str) -> bool:
        """Manually switch to a specific provider."""
        async with self._lock:
            for i, (name, provider) in enumerate(self.providers):
                if name == provider_name:
                    if self.health_checker.is_available(name):
                        self._current_provider_index = i
                        self._last_failover_time = time.time()
                        logger.info(f"Manually switched to provider: {provider_name}")
                        return True
                    else:
                        logger.warning(f"Provider {provider_name} is not available")
                        return False
            return False

    def get_provider_status(self) -> dict[str, Any]:
        """Get status of all providers."""
        status = {}
        for name, _ in self.providers:
            health = self.health_checker.get_health_data(name)
            if health:
                status[name] = {
                    "status": health.status.value,
                    "consecutive_failures": health.consecutive_failures,
                    "consecutive_successes": health.consecutive_successes,
                    "avg_response_time": health.avg_response_time,
                    "total_requests": health.total_requests,
                    "failed_requests": health.failed_requests,
                    "is_current": name == self.current_provider_name,
                }
            else:
                status[name] = {
                    "status": "unknown",
                    "is_current": name == self.current_provider_name,
                }
        return status


class AdaptiveProviderPool:
    """
    Adaptive provider pool with intelligent request distribution.
    
    Distributes requests across multiple providers based on health
    and performance metrics.
    """

    def __init__(
        self,
        providers: list[tuple[str, Any]],
        health_checker: ProviderHealthChecker | None = None,
    ):
        self.providers = providers
        self.health_checker = health_checker or ProviderHealthChecker()
        self._weights: dict[str, float] = {name: 1.0 for name, _ in providers}

    def _calculate_weights(self) -> dict[str, float]:
        """Calculate provider weights based on health."""
        weights = {}
        total = 0

        for name, _ in self.providers:
            health = self.health_checker.get_health_data(name)
            if health is None or health.status == ProviderStatus.HEALTHY:
                weight = 1.0
            elif health.status == ProviderStatus.DEGRADED:
                weight = 0.5
            else:
                weight = 0.1

            if health and health.avg_response_time > 0:
                weight *= min(1.0, 10.0 / max(health.avg_response_time, 1.0))

            weights[name] = weight
            total += weight

        for name in weights:
            weights[name] = weights[name] / total if total > 0 else 0

        return weights

    def get_provider(self) -> tuple[str, Any]:
        """Get a provider based on weighted selection."""
        import random
        self._weights = self._calculate_weights()

        names = list(self._weights.keys())
        weights = list(self._weights.values())

        selected = random.choices(names, weights=weights, k=1)[0]

        for name, provider in self.providers:
            if name == selected:
                return (name, provider)

        return self.providers[0]
