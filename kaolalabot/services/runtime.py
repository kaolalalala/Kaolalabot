"""Runtime service registry for optional system services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class RuntimeServices:
    """Container for long-running optional services."""

    mcp: Optional[object] = None
    scheduler: Optional[object] = None
    heartbeat: Optional[object] = None
    clawhub: Optional[object] = None
    openclaw: Optional[object] = None


_runtime_services: RuntimeServices | None = None


def set_runtime_services(services: RuntimeServices) -> None:
    """Set global runtime service container."""
    global _runtime_services
    _runtime_services = services


def get_runtime_services() -> RuntimeServices:
    """Get global runtime service container."""
    global _runtime_services
    if _runtime_services is None:
        _runtime_services = RuntimeServices()
    return _runtime_services
