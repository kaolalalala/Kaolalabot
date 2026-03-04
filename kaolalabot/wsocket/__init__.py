"""Socket.IO module."""

from kaolalabot.wsocket.handler import GatewayNamespace, LegacyAgentNamespace, register_handlers

__all__ = ["GatewayNamespace", "LegacyAgentNamespace", "register_handlers"]
