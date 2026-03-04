import pytest

from kaolalabot.services.openclaw_local import OpenClawLocalService


@pytest.mark.asyncio
async def test_openclaw_local_service_status_and_lifecycle():
    service = OpenClawLocalService(gateway_url="http://127.0.0.1:18789", token="t")
    before = service.status()
    assert before["running"] is False
    assert before["token_configured"] is True

    await service.start()
    assert service.status()["running"] is True

    await service.stop()
    assert service.status()["running"] is False


@pytest.mark.asyncio
async def test_openclaw_local_service_health_pass_through(monkeypatch):
    service = OpenClawLocalService()

    async def _fake_request(method, path, json=None):
        assert method == "GET"
        assert path == "/health"
        return {"ok": True, "data": {"status": "ok"}}

    monkeypatch.setattr(service, "_request", _fake_request)
    out = await service.health()
    assert out["ok"] is True
    assert out["gateway"]["status"] == "ok"


@pytest.mark.asyncio
async def test_openclaw_local_service_invoke_payload(monkeypatch):
    service = OpenClawLocalService(session_key="abc")

    async def _fake_request(method, path, json=None):
        assert method == "POST"
        assert path == "/tools/invoke"
        assert json["tool"] == "exec"
        assert json["args"]["command"] == "dir"
        assert json["sessionKey"] == "abc"
        return {"ok": True, "data": {"ok": True}}

    monkeypatch.setattr(service, "_request", _fake_request)
    out = await service.invoke_tool("exec", args={"command": "dir"})
    assert out["ok"] is True
