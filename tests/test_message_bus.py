import pytest

from kaolalabot.bus.events import InboundMessage
from kaolalabot.bus.queue import MessageBus


@pytest.mark.asyncio
async def test_message_bus_has_bounded_queues_by_default() -> None:
    bus = MessageBus()
    assert bus.inbound.maxsize == 1000
    assert bus.outbound.maxsize == 1000


@pytest.mark.asyncio
async def test_publish_and_consume_inbound_message() -> None:
    bus = MessageBus()
    msg = InboundMessage(
        channel="web",
        sender_id="u1",
        chat_id="c1",
        content="hello",
    )
    await bus.publish_inbound(msg)
    got = await bus.consume_inbound()
    assert got.content == "hello"
    assert got.session_key == "web:c1"
