from kaolalabot.services.heartbeat import HeartbeatService


def test_heartbeat_payload_contains_health():
    svc = HeartbeatService(endpoint='http://example.com', health_provider=lambda: {'ready': True})
    payload = svc.build_payload()
    assert payload['status'] == 'running'
    assert payload['health']['ready'] is True
    assert 'timestamp' in payload
