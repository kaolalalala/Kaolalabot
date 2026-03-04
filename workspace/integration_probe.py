import asyncio
import aiohttp
from kaolalabot.bus.queue import MessageBus
from kaolalabot.channels.manager import ChannelManager
from kaolalabot.config.schema import Config


async def main():
    cfg = Config()
    cfg.channels.feishu.enabled = False
    cfg.channels.voice.enabled = False
    cfg.channels.dingtalk.enabled = True
    cfg.channels.dingtalk.callback_host = '127.0.0.1'
    cfg.channels.dingtalk.callback_port = 18792
    cfg.channels.dingtalk.callback_path = '/callback'

    bus = MessageBus()
    manager = ChannelManager(cfg, bus)
    await manager.start_all()

    async with aiohttp.ClientSession() as s:
        resp = await s.post('http://127.0.0.1:18792/callback', json={
            'text': {'content': 'integration ping'},
            'senderStaffId': 'u-integration',
            'conversationId': 'c-integration',
        })
        assert resp.status == 200

    inbound = await asyncio.wait_for(bus.consume_inbound(), timeout=3)
    assert inbound.channel == 'dingtalk'
    assert inbound.content == 'integration ping'

    await manager.stop_all()
    print('integration.dingtalk_callback=PASS')


asyncio.run(main())
