from kaolalabot.gateway.auth import AuthMode, GatewayAuth


def test_password_auth_works_when_password_provided() -> None:
    auth = GatewayAuth(mode=AuthMode.PASSWORD, password="secret123")
    result = auth.authenticate(password="secret123", remote_addr="127.0.0.1")
    assert result.success


def test_websocket_bearer_header_is_accepted() -> None:
    auth = GatewayAuth(mode=AuthMode.TOKEN, token="token-abc")
    result = auth.authenticate_websocket(
        token=None,
        headers={"authorization": "Bearer token-abc"},
        remote_addr="127.0.0.1",
    )
    assert result.success


def test_invalid_attempts_trigger_rate_limit() -> None:
    auth = GatewayAuth(mode=AuthMode.TOKEN, token="token-abc")
    for _ in range(5):
        result = auth.authenticate(token="wrong", remote_addr="10.0.0.2")
        assert not result.success
    limited = auth.authenticate(token="wrong", remote_addr="10.0.0.2")
    assert not limited.success
    assert "Too many failed attempts" in (limited.error or "")
