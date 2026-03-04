"""Complete monitoring and alerting system."""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from loguru import logger


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class Metric:
    """A metric data point."""
    name: str
    value: float
    metric_type: MetricType
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class Alert:
    """An alert notification."""
    id: str
    level: AlertLevel
    title: str
    message: str
    source: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: float | None = None


class MetricsCollector:
    """
    Metrics collector for system monitoring.
    
    Collects and stores system metrics.
    """

    def __init__(self):
        self._metrics: dict[str, list[Metric]] = {}
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def record_counter(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a counter metric."""
        async with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value
            
            metric = Metric(
                name=name,
                value=self._counters[name],
                metric_type=MetricType.COUNTER,
                labels=labels or {},
            )
            self._metrics.setdefault(name, []).append(metric)

    async def record_gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a gauge metric."""
        async with self._lock:
            self._gauges[name] = value
            
            metric = Metric(
                name=name,
                value=value,
                metric_type=MetricType.GAUGE,
                labels=labels or {},
            )
            self._metrics.setdefault(name, []).append(metric)

    async def record_histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a histogram metric."""
        metric = Metric(
            name=name,
            value=value,
            metric_type=MetricType.HISTOGRAM,
            labels=labels or {},
        )
        async with self._lock:
            self._metrics.setdefault(name, []).append(metric)

    async def get_metric(self, name: str) -> list[Metric]:
        """Get metrics by name."""
        async with self._lock:
            return self._metrics.get(name, [])

    async def get_latest(self, name: str) -> float | None:
        """Get latest value for a metric."""
        metrics = await self.get_metric(name)
        if metrics:
            return metrics[-1].value
        return None


class AlertManager:
    """
    Alert manager for handling alerts.
    
    Manages alert creation, notification, and resolution.
    """

    def __init__(self):
        self._alerts: dict[str, Alert] = {}
        self._handlers: list[Callable[[Alert], Awaitable[None]]] = []
        self._lock = asyncio.Lock()

    def register_handler(self, handler: Callable[[Alert], Awaitable[None]]) -> None:
        """Register an alert handler."""
        self._handlers.append(handler)
        logger.info("Registered alert handler")

    async def create_alert(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> Alert:
        """Create a new alert."""
        alert_id = f"alert:{source}:{int(time.time())}"
        
        alert = Alert(
            id=alert_id,
            level=level,
            title=title,
            message=message,
            source=source,
            metadata=metadata or {},
        )
        
        async with self._lock:
            self._alerts[alert_id] = alert
        
        logger.log(
            "WARNING" if level == AlertLevel.WARNING else "ERROR" if level in (AlertLevel.ERROR, AlertLevel.CRITICAL) else "INFO",
            f"Alert: {title} - {message}"
        )
        
        for handler in self._handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")
        
        return alert

    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        async with self._lock:
            if alert_id in self._alerts:
                self._alerts[alert_id].resolved = True
                self._alerts[alert_id].resolved_at = time.time()
                return True
        return False

    async def get_active_alerts(self) -> list[Alert]:
        """Get all active (unresolved) alerts."""
        async with self._lock:
            return [a for a in self._alerts.values() if not a.resolved]

    async def get_alerts_by_level(self, level: AlertLevel) -> list[Alert]:
        """Get alerts by level."""
        async with self._lock:
            return [a for a in self._alerts.values() if a.level == level and not a.resolved]


class MonitoringDashboard:
    """
    Complete monitoring dashboard.
    
    Provides system-wide monitoring, metrics, and alerting.
    """

    def __init__(self):
        self.metrics = MetricsCollector()
        self.alerts = AlertManager()
        self._monitoring = False
        self._monitor_tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start the monitoring system."""
        self._monitoring = True
        logger.info("Monitoring dashboard started")

    async def stop(self) -> None:
        """Stop the monitoring system."""
        self._monitoring = False
        for task in self._monitor_tasks:
            task.cancel()
        logger.info("Monitoring dashboard stopped")

    async def record_request(
        self,
        endpoint: str,
        duration: float,
        status: int,
    ) -> None:
        """Record an API request."""
        await self.metrics.record_counter(
            "requests_total",
            labels={"endpoint": endpoint, "status": str(status)}
        )
        await self.metrics.record_histogram(
            "request_duration_seconds",
            duration,
            labels={"endpoint": endpoint}
        )

    async def record_error(
        self,
        error_type: str,
        message: str,
    ) -> None:
        """Record an error."""
        await self.metrics.record_counter(
            "errors_total",
            labels={"type": error_type}
        )
        
        level = AlertLevel.ERROR if "timeout" not in message.lower() else AlertLevel.WARNING
        
        await self.alerts.create_alert(
            level=level,
            title=f"Error: {error_type}",
            message=message,
            source="system",
        )

    async def record_provider_metrics(
        self,
        provider: str,
        success: bool,
        duration: float,
    ) -> None:
        """Record provider metrics."""
        status = "success" if success else "failure"
        
        await self.metrics.record_counter(
            "provider_requests_total",
            labels={"provider": provider, "status": status}
        )
        
        if success:
            await self.metrics.record_histogram(
                "provider_request_duration_seconds",
                duration,
                labels={"provider": provider}
            )

    async def check_system_health(self) -> dict[str, Any]:
        """Check overall system health."""
        active_alerts = await self.alerts.get_active_alerts()
        
        critical_count = len([a for a in active_alerts if a.level == AlertLevel.CRITICAL])
        error_count = len([a for a in active_alerts if a.level == AlertLevel.ERROR])
        
        health_status = "healthy"
        if critical_count > 0:
            health_status = "critical"
        elif error_count > 0:
            health_status = "degraded"
        elif active_alerts:
            health_status = "warning"
        
        return {
            "status": health_status,
            "active_alerts": len(active_alerts),
            "critical_alerts": critical_count,
            "error_alerts": error_count,
            "timestamp": datetime.now().isoformat(),
        }

    async def get_metrics_summary(self) -> dict[str, Any]:
        """Get metrics summary."""
        return {
            "requests_total": await self.metrics.get_latest("requests_total"),
            "errors_total": await self.metrics.get_latest("errors_total"),
            "timestamp": datetime.now().isoformat(),
        }

    async def get_alert_summary(self) -> dict[str, Any]:
        """Get alert summary."""
        active = await self.alerts.get_active_alerts()
        
        return {
            "active_count": len(active),
            "by_level": {
                level.value: len([a for a in active if a.level == level])
                for level in AlertLevel
            },
            "timestamp": datetime.now().isoformat(),
        }


class AlertNotifier:
    """
    Alert notifier for sending notifications.
    
    Supports multiple notification channels.
    """

    def __init__(self):
        self._webhook_urls: dict[str, str] = {}

    def add_webhook(self, name: str, url: str) -> None:
        """Add a webhook for notifications."""
        self._webhook_urls[name] = url

    async def send_notification(self, alert: Alert) -> None:
        """Send alert notification."""
        message = f"[{alert.level.value.upper()}] {alert.title}\n{alert.message}"
        
        logger.info(f"Alert notification: {message}")
        
        for name, url in self._webhook_urls.items():
            try:
                await self._send_webhook(url, alert)
            except Exception as e:
                logger.error(f"Failed to send webhook to {name}: {e}")

    async def _send_webhook(self, url: str, alert: Alert) -> None:
        """Send webhook notification."""
        import aiohttp
        
        payload = {
            "alert_id": alert.id,
            "level": alert.level.value,
            "title": alert.title,
            "message": alert.message,
            "source": alert.source,
            "timestamp": datetime.fromtimestamp(alert.timestamp).isoformat(),
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status >= 400:
                    logger.warning(f"Webhook returned status {response.status}")


_global_dashboard: MonitoringDashboard | None = None


def get_monitoring_dashboard() -> MonitoringDashboard:
    """Get the global monitoring dashboard instance."""
    global _global_dashboard
    if _global_dashboard is None:
        _global_dashboard = MonitoringDashboard()
    return _global_dashboard
