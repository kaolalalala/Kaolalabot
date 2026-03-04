"""Rate limiting system with token bucket and leaky bucket algorithms."""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


class RateLimitStrategy(Enum):
    """Rate limiting algorithm strategies."""
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
    enabled: bool = True


@dataclass
class RateLimitStatus:
    """Current rate limit status for a key."""
    key: str
    tokens: float
    last_refill_time: float
    requests_count: int = 0
    blocked_count: int = 0


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter implementation.
    
    Allows burst traffic up to bucket size while maintaining
    average rate over time.
    """

    def __init__(
        self,
        rate: float,
        burst: int,
        refill_interval: float = 1.0,
    ):
        self.rate = rate
        self.burst = burst
        self.refill_interval = refill_interval
        self._buckets: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def _get_bucket(self, key: str) -> dict[str, Any]:
        """Get or create a bucket for the given key."""
        now = time.time()
        if key not in self._buckets:
            self._buckets[key] = {
                "tokens": float(self.burst),
                "last_refill": now,
            }
        else:
            bucket = self._buckets[key]
            elapsed = now - bucket["last_refill"]
            tokens_to_add = elapsed * self.rate
            bucket["tokens"] = min(self.burst, bucket["tokens"] + tokens_to_add)
            bucket["last_refill"] = now
        return self._buckets[key]

    async def acquire(self, key: str, tokens: int = 1) -> bool:
        """
        Try to acquire tokens from the bucket.
        
        Returns True if tokens were acquired, False if rate limited.
        """
        async with self._lock:
            bucket = await self._get_bucket(key)
            if bucket["tokens"] >= tokens:
                bucket["tokens"] -= tokens
                return True
            return False

    async def wait_for_token(self, key: str, tokens: int = 1, timeout: float = 30.0) -> bool:
        """Wait for tokens to become available."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if await self.acquire(key, tokens):
                return True
            await asyncio.sleep(0.1)
        return False


class LeakyBucketRateLimiter:
    """
    Leaky bucket rate limiter implementation.
    
    Processes requests at a constant rate, smoothing out bursts.
    """

    def __init__(
        self,
        rate: float,
        capacity: int,
    ):
        self.rate = rate
        self.capacity = capacity
        self._buckets: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def _get_bucket(self, key: str) -> dict[str, Any]:
        """Get or create a bucket for the given key."""
        now = time.time()
        if key not in self._buckets:
            self._buckets[key] = {
                "level": 0.0,
                "last_update": now,
            }
        else:
            bucket = self._buckets[key]
            elapsed = now - bucket["last_update"]
            bucket["level"] = max(0.0, bucket["level"] - (elapsed * self.rate))
            bucket["last_update"] = now
        return self._buckets[key]

    async def acquire(self, key: str, amount: float = 1.0) -> bool:
        """
        Try to add to the bucket.
        
        Returns True if request was accepted, False if rate limited.
        """
        async with self._lock:
            bucket = await self._get_bucket(key)
            if bucket["level"] + amount <= self.capacity:
                bucket["level"] += amount
                return True
            return False

    async def wait_for_space(self, key: str, amount: float = 1.0, timeout: float = 30.0) -> bool:
        """Wait for space to become available in the bucket."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if await self.acquire(key, amount):
                return True
            await asyncio.sleep(0.1)
        return False


class MultiDimensionalRateLimiter:
    """
    Multi-dimensional rate limiter supporting various rate limit keys.
    
    Supports rate limiting by:
    - User ID
    - Channel
    - API endpoint
    - Global
    """

    def __init__(
        self,
        config: RateLimitConfig | None = None,
    ):
        self.config = config or RateLimitConfig()
        
        self._user_limiter = TokenBucketRateLimiter(
            rate=self.config.requests_per_minute / 60.0,
            burst=self.config.burst_size,
        )
        self._channel_limiter = TokenBucketRateLimiter(
            rate=self.config.requests_per_minute * 2 / 60.0,
            burst=self.config.burst_size * 2,
        )
        self._global_limiter = TokenBucketRateLimiter(
            rate=self.config.requests_per_hour / 3600.0,
            burst=self.config.burst_size,
        )
        
        self._status: dict[str, RateLimitStatus] = {}
        self._lock = asyncio.Lock()

    async def check_rate_limit(
        self,
        user_id: str | None = None,
        channel: str | None = None,
        endpoint: str | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Check if request is within rate limits.
        
        Returns (is_allowed, rate_limit_info)
        """
        if not self.config.enabled:
            return True, {"limited": False}

        violations = []
        
        if user_id:
            if not await self._user_limiter.acquire(f"user:{user_id}"):
                violations.append("user")
        
        if channel:
            if not await self._channel_limiter.acquire(f"channel:{channel}"):
                violations.append("channel")

        if not await self._global_limiter.acquire("global"):
            violations.append("global")

        is_allowed = len(violations) == 0

        return is_allowed, {
            "limited": not is_allowed,
            "violations": violations,
            "retry_after": self._calculate_retry_after(),
        }

    async def wait_and_acquire(
        self,
        user_id: str | None = None,
        channel: str | None = None,
        endpoint: str | None = None,
        timeout: float = 30.0,
    ) -> bool:
        """Wait for rate limit to clear and acquire."""
        if not self.config.enabled:
            return True

        start_time = time.time()
        
        while time.time() - start_time < timeout:
            is_allowed, _ = await self.check_rate_limit(user_id, channel, endpoint)
            if is_allowed:
                return True
            await asyncio.sleep(0.5)

        return False

    def _calculate_retry_after(self) -> int:
        """Calculate recommended retry-after seconds."""
        return 60

    async def get_status(self, key: str) -> RateLimitStatus | None:
        """Get rate limit status for a key."""
        return self._status.get(key)

    def get_config(self) -> RateLimitConfig:
        """Get current rate limit configuration."""
        return self.config

    def update_config(self, config: RateLimitConfig) -> None:
        """Update rate limit configuration."""
        self.config = config
        self._user_limiter = TokenBucketRateLimiter(
            rate=config.requests_per_minute / 60.0,
            burst=config.burst_size,
        )
        self._channel_limiter = TokenBucketRateLimiter(
            rate=config.requests_per_minute * 2 / 60.0,
            burst=config.burst_size * 2,
        )
        logger.info(f"Rate limit config updated: {config}")


class RateLimitMiddleware:
    """
    Middleware for applying rate limits to requests.
    
    Can be integrated into the message bus or gateway.
    """

    def __init__(self, limiter: MultiDimensionalRateLimiter | None = None):
        self.limiter = limiter or MultiDimensionalRateLimiter()

    async def check_request(
        self,
        user_id: str | None = None,
        channel: str | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """Check if a request should be rate limited."""
        return await self.limiter.check_rate_limit(user_id=user_id, channel=channel)

    async def process_message(
        self,
        user_id: str | None = None,
        channel: str | None = None,
        content: str = "",
    ) -> tuple[bool, str | None]:
        """
        Process a message through rate limiting.
        
        Returns (should_proceed, rejection_message)
        """
        is_allowed, info = await self.check_request(user_id, channel)
        
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for user={user_id}, channel={channel}: {info}")
            return False, f"Rate limit exceeded. Please try again later. Violations: {info['violations']}"
        
        return True, None
