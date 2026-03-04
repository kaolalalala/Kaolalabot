import asyncio

import pytest

from kaolalabot.services.mcp import MCPPacket, MCPService


def test_mcp_packet_roundtrip():
    p = MCPPacket(packet_type='event', payload={'event': 'chat_message', 'content': 'hi'}, request_id='r1')
    decoded = MCPPacket.from_bytes(p.to_bytes())
    assert decoded.packet_type == 'event'
    assert decoded.payload['content'] == 'hi'
    assert decoded.request_id == 'r1'


@pytest.mark.asyncio
async def test_mcp_event_dispatch():
    svc = MCPService('127.0.0.1', 25575)
    seen = {'value': ''}

    async def on_event(payload):
        seen['value'] = payload.get('content', '')

    svc.on('chat_message', on_event)
    await svc._handle_packet(MCPPacket(packet_type='event', payload={'event': 'chat_message', 'content': 'hello'}))
    assert seen['value'] == 'hello'
