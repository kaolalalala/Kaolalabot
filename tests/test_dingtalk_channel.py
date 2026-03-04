from kaolalabot.bus.queue import MessageBus
from kaolalabot.channels.dingtalk import DingTalkChannel
from kaolalabot.config.schema import DingTalkConfig


def test_build_webhook_url_contains_access_token():
    channel = DingTalkChannel(DingTalkConfig(webhook_access_token='token123'), MessageBus())
    url = channel._build_webhook_url()
    assert url is not None
    assert 'access_token=token123' in url


def test_extract_callback_fields():
    payload = {
        'text': {'content': 'hello dingtalk'},
        'senderStaffId': 'u1',
        'conversationId': 'c1',
    }
    assert DingTalkChannel._extract_text(payload) == 'hello dingtalk'
    assert DingTalkChannel._extract_sender(payload) == 'u1'
    assert DingTalkChannel._extract_chat_id(payload, 'u1') == 'c1'
