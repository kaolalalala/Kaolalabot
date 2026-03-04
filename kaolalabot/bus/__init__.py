"""Message bus module for decoupled channel-agent communication."""

from kaolalabot.bus.events import InboundMessage, OutboundMessage
from kaolalabot.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
