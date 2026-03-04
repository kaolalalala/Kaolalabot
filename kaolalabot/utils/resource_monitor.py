"""Resource monitoring and limiting system."""

import asyncio
import os
import psutil
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class ResourceThresholds:
    """Resource usage thresholds."""
    cpu_percent: float = 80.0
    memory_percent: float = 80.0
    disk_io_mb_per_sec: float = 100.0
    max_concurrent_requests: int = 100


@dataclass
class ResourceUsage:
    """Current resource usage."""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    disk_read_mb_per_sec: float = 0.0
    disk_write_mb_per_sec: float = 0.0
    active_requests: int = 0
    timestamp: float = field(default_factory=time.time)


class ResourceMonitor:
    """
    System resource monitor.
    
    Monitors CPU, memory, disk I/O, and tracks active requests.
    """

    def __init__(
        self,
        thresholds: ResourceThresholds | None = None,
        check_interval: float = 5.0,
    ):
        self.thresholds = thresholds or ResourceThresholds()
        self.check_interval = check_interval
        self._usage_history: list[ResourceUsage] = []
        self._max_history = 100
        self._active_requests = 0
        self._lock = asyncio.Lock()
        self._monitoring = False

    async def start_monitoring(self) -> None:
        """Start background resource monitoring."""
        self._monitoring = True
        asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        self._monitoring = False

    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._monitoring:
            try:
                await self._collect_usage()
            except Exception as e:
                logger.warning(f"Resource monitoring error: {e}")
            await asyncio.sleep(self.check_interval)

    async def _collect_usage(self) -> None:
        """Collect current resource usage."""
        process = psutil.Process(os.getpid())
        
        cpu_percent = process.cpu_percent(interval=0.1)
        memory_info = process.memory_info()
        memory_percent = process.memory_percent()
        
        io_counters = process.io_counters()
        disk_read = io_counters.read_bytes / (1024 * 1024)
        disk_write = io_counters.write_bytes / (1024 * 1024)

        usage = ResourceUsage(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_mb=memory_info.rss / (1024 * 1024),
            disk_read_mb_per_sec=disk_read / self.check_interval,
            disk_write_mb_per_sec=disk_write / self.check_interval,
            active_requests=self._active_requests,
        )

        async with self._lock:
            self._usage_history.append(usage)
            if len(self._usage_history) > self._max_history:
                self._usage_history = self._usage_history[-self._max_history:]

    def get_current_usage(self) -> ResourceUsage:
        """Get current resource usage."""
        if self._usage_history:
            return self._usage_history[-1]
        return ResourceUsage()

    def get_average_usage(self, seconds: int = 60) -> ResourceUsage:
        """Get average resource usage over time period."""
        cutoff = time.time() - seconds
        
        recent = [u for u in self._usage_history if u.timestamp > cutoff]
        
        if not recent:
            return ResourceUsage()
        
        return ResourceUsage(
            cpu_percent=sum(u.cpu_percent for u in recent) / len(recent),
            memory_percent=sum(u.memory_percent for u in recent) / len(recent),
            memory_used_mb=sum(u.memory_used_mb for u in recent) / len(recent),
            active_requests=sum(u.active_requests for u in recent) / len(recent),
        )

    async def increment_requests(self) -> int:
        """Increment active request count."""
        async with self._lock:
            self._active_requests += 1
            return self._active_requests

    async def decrement_requests(self) -> int:
        """Decrement active request count."""
        async with self._lock:
            self._active_requests = max(0, self._active_requests - 1)
            return self._active_requests


class ResourceGuard:
    """
    Resource guard for limiting resource usage.
    
    Provides resource throttling and circuit breaking.
    """

    def __init__(
        self,
        monitor: ResourceMonitor,
        thresholds: ResourceThresholds | None = None,
    ):
        self.monitor = monitor
        self.thresholds = thresholds or ResourceThresholds()
        self._circuit_open = False
        self._circuit_open_time = 0.0
        self._circuit_reset_time = 60.0

    async def check_resources(self) -> tuple[bool, str]:
        """
        Check if resources are available.
        
        Returns (can_proceed, reason)
        """
        if self._circuit_open:
            if time.time() - self._circuit_open_time > self._circuit_reset_time:
                self._circuit_open = False
                logger.info("Circuit breaker reset")
            else:
                return False, "Circuit breaker is open"

        usage = self.monitor.get_current_usage()

        if usage.cpu_percent > self.thresholds.cpu_percent:
            self._trigger_circuit()
            return False, f"CPU usage too high: {usage.cpu_percent:.1f}%"

        if usage.memory_percent > self.thresholds.memory_percent:
            self._trigger_circuit()
            return False, f"Memory usage too high: {usage.memory_percent:.1f}%"

        if usage.active_requests >= self.thresholds.max_concurrent_requests:
            return False, f"Too many concurrent requests: {usage.active_requests}"

        return True, ""

    def _trigger_circuit(self) -> None:
        """Trigger circuit breaker."""
        if not self._circuit_open:
            self._circuit_open = True
            self._circuit_open_time = time.time()
            logger.warning("Circuit breaker triggered due to high resource usage")

    def get_status(self) -> dict[str, Any]:
        """Get resource guard status."""
        usage = self.monitor.get_current_usage()
        
        return {
            "circuit_open": self._circuit_open,
            "cpu_percent": usage.cpu_percent,
            "cpu_threshold": self.thresholds.cpu_percent,
            "memory_percent": usage.memory_percent,
            "memory_threshold": self.thresholds.memory_percent,
            "active_requests": usage.active_requests,
            "max_concurrent": self.thresholds.max_concurrent_requests,
        }


class ResourceLimiter:
    """
    Request resource limiter with queuing support.
    
    Limits resource usage per user or globally.
    """

    def __init__(
        self,
        monitor: ResourceMonitor,
        max_per_user: int = 10,
        max_global: int = 100,
    ):
        self.monitor = monitor
        self.max_per_user = max_per_user
        self.max_global = max_global
        self._user_requests: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def acquire(
        self,
        user_id: str,
        timeout: float = 30.0,
    ) -> bool:
        """
        Try to acquire a resource slot.
        
        Returns True if acquired, False if limited.
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            async with self._lock:
                current = self._user_requests.get(user_id, 0)
                
                if current >= self.max_per_user:
                    await asyncio.sleep(0.5)
                    continue
                
                usage = self.monitor.get_current_usage()
                if usage.active_requests >= self.max_global:
                    await asyncio.sleep(0.5)
                    continue
                
                self._user_requests[user_id] = current + 1
                return True

        return False

    async def release(self, user_id: str) -> None:
        """Release a resource slot."""
        async with self._lock:
            current = self._user_requests.get(user_id, 0)
            self._user_requests[user_id] = max(0, current - 1)

    async def get_user_count(self, user_id: str) -> int:
        """Get current request count for a user."""
        async with self._lock:
            return self._user_requests.get(user_id, 0)
