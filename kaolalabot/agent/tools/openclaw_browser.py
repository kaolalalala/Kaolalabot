"""OpenClaw dedicated browser tool bridge."""

from __future__ import annotations

import json
from typing import Any, Literal

from kaolalabot.agent.tools.base import Tool

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


BrowserTarget = Literal["host", "node", "sandbox"]


class OpenClawBrowserTool(Tool):
    """Invoke OpenClaw browser tool via gateway /tools/invoke."""

    def __init__(
        self,
        gateway_url: str = "http://127.0.0.1:18789",
        token: str = "",
        session_key: str = "main",
        profile: str = "openclaw",
        target: BrowserTarget = "host",
        node: str = "",
        timeout_ms: int = 15000,
    ):
        self.gateway_url = gateway_url.rstrip("/")
        self.token = token
        self.session_key = session_key
        self.profile = profile
        self.target = target
        self.node = node
        self.timeout_ms = max(3000, int(timeout_ms))

    @property
    def name(self) -> str:
        return "openclaw_browser"

    @property
    def description(self) -> str:
        return (
            "Control OpenClaw dedicated browser profiles through gateway browser tool. "
            "Supports actions like status/start/open/navigate/snapshot/screenshot/act/tabs."
        )

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "browser tool action, e.g. status/start/open/navigate/snapshot/act/tabs",
                        },
                        "target_url": {"type": "string", "description": "URL for open/navigate"},
                        "target_id": {"type": "string", "description": "tab target id for focus/close"},
                        "profile": {"type": "string", "description": "browser profile name, default openclaw"},
                        "target": {"type": "string", "description": "host|node|sandbox"},
                        "node": {"type": "string", "description": "node id when target=node"},
                        "request": {"type": "object", "description": "nested action payload for act"},
                    },
                    "required": ["action"],
                },
            },
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        if not params.get("action"):
            return ["action is required"]
        return []

    async def execute(
        self,
        action: str,
        target_url: str | None = None,
        target_id: str | None = None,
        profile: str | None = None,
        target: BrowserTarget | None = None,
        node: str | None = None,
        request: dict[str, Any] | None = None,
        timeout_ms: int | None = None,
    ) -> str:
        if not AIOHTTP_AVAILABLE:
            return "Error: aiohttp is required for openclaw_browser tool"

        args: dict[str, Any] = {
            "action": action,
            "profile": profile or self.profile,
            "target": target or self.target,
        }
        if target_url:
            args["targetUrl"] = target_url
        if target_id:
            args["targetId"] = target_id
        node_value = node or self.node
        if node_value:
            args["node"] = node_value
        if request:
            args["request"] = request
        if timeout_ms:
            args["timeoutMs"] = int(timeout_ms)

        payload = {"tool": "browser", "args": args, "sessionKey": self.session_key}
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            req_timeout = aiohttp.ClientTimeout(total=max(5, (timeout_ms or self.timeout_ms) / 1000 + 5))
            async with aiohttp.ClientSession(timeout=req_timeout) as session:
                async with session.post(f"{self.gateway_url}/tools/invoke", headers=headers, json=payload) as resp:
                    data = await resp.json(content_type=None)
                    if resp.status != 200:
                        return f"Error: OpenClaw browser invoke failed (HTTP {resp.status}): {data}"
                    if isinstance(data, dict) and data.get("ok") is False:
                        return f"Error: OpenClaw browser error: {data.get('error')}"
                    result = data.get("result") if isinstance(data, dict) else data
                    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            return f"Error: OpenClaw browser request failed: {exc}"
