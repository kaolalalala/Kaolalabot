import pytest

from kaolalabot.bus.events import OutboundMessage
from kaolalabot.bus.queue import MessageBus
from kaolalabot.channels.web import WebChannel


@pytest.mark.asyncio
async def test_web_channel_uses_registered_sender() -> None:
    bus = MessageBus()
    channel = WebChannel(config={}, bus=bus)
    delivered: list[str] = []

    async def sender(msg: OutboundMessage) -> None:
        delivered.append(msg.content)

    channel.set_sender(sender)
    await channel.send(OutboundMessage(channel="web", chat_id="s1", content="ok"))
    assert delivered == ["ok"]
