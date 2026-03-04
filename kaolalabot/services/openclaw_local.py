"""OpenClaw local gateway integration service."""

from __future__ import annotations

from typing import Any

from loguru import logger

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


class OpenClawLocalService:
    """Client for local OpenClaw gateway APIs."""

    def __init__(
        self,
        gateway_url: str = "http://127.0.0.1:18789",
        token: str = "",
        timeout_seconds: int = 15,
        session_key: str = "main",
    ):
        self.gateway_url = gateway_url.rstrip("/")
        self.token = token
        self.timeout_seconds = max(3, int(timeout_seconds))
        self.session_key = session_key
        self._running = False

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    def status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "gateway_url": self.gateway_url,
            "session_key": self.session_key,
            "token_configured": bool(self.token),
        }

    async def health(self) -> dict[str, Any]:
        result = await self._request("GET", "/health")
        if result.get("ok"):
            return {"ok": True, "gateway": result.get("data")}
        return result

    async def invoke_tool(
        self,
        tool: str,
        args: dict[str, Any] | None = None,
        action: str | None = None,
        session_key: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tool": tool,
            "args": args or {},
            "sessionKey": session_key or self.session_key,
        }
        if action:
            payload["action"] = action
        return await self._request("POST", "/tools/invoke", json=payload)

    async def _request(self, method: str, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        if not AIOHTTP_AVAILABLE:
            return {"ok": False, "error": "aiohttp is required"}
        url = f"{self.gateway_url}{path}"
        headers: dict[str, str] = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(method, url, headers=headers, json=json) as resp:
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:
                        data = await resp.text()
                    if 200 <= resp.status < 300:
                        return {"ok": True, "status": resp.status, "data": data}
                    return {"ok": False, "status": resp.status, "error": data}
        except Exception as exc:
            logger.warning("OpenClaw local request failed: {}", exc)
            return {"ok": False, "error": str(exc)}

