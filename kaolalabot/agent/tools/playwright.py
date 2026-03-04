"""Playwright browser automation tool."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kaolalabot.agent.tools.base import Tool

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


class PlaywrightTool(Tool):
    """Automate browser actions with native Playwright or OpenClaw backend."""

    def __init__(
        self,
        workspace: Path,
        backend: str = "native",
        timeout_seconds: int = 30,
        headless: bool = True,
        channel: str = "msedge",
        screenshot_dir: str = "workspace/artifacts/playwright",
        openclaw_gateway_url: str = "http://127.0.0.1:18789",
        openclaw_token: str = "",
        openclaw_session_key: str = "main",
        openclaw_tool: str = "playwright",
        openclaw_host: str = "sandbox",
        openclaw_security: str = "allowlist",
        openclaw_ask: str = "on-miss",
        openclaw_node: str = "",
        openclaw_elevated: bool = False,
    ):
        self.workspace = workspace
        self.backend = backend
        self.timeout_seconds = max(5, int(timeout_seconds))
        self.headless = bool(headless)
        self.channel = (channel or "").strip()
        self.screenshot_dir = screenshot_dir
        self.openclaw_gateway_url = openclaw_gateway_url.rstrip("/")
        self.openclaw_token = openclaw_token
        self.openclaw_session_key = openclaw_session_key
        self.openclaw_tool = openclaw_tool
        self.openclaw_host = openclaw_host
        self.openclaw_security = openclaw_security
        self.openclaw_ask = openclaw_ask
        self.openclaw_node = openclaw_node
        self.openclaw_elevated = openclaw_elevated

    @property
    def name(self) -> str:
        return "playwright"

    @property
    def description(self) -> str:
        return (
            "Automate browser tasks: open page, click elements, fill forms, submit and scrape. "
            "Use actions[] script with action keys: navigate/click/fill/press/wait/screenshot/content/title/extract_text."
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
                        "url": {"type": "string", "description": "Initial URL to open"},
                        "actions": {
                            "type": "array",
                            "description": "Action list for browser automation",
                            "items": {"type": "object"},
                        },
                        "script": {
                            "type": "object",
                            "description": "Complete script object: {url, actions, headless, timeout}",
                        },
                        "timeout": {"type": "integer", "description": "Timeout seconds"},
                        "headless": {"type": "boolean", "description": "Headless mode"},
                        "channel": {"type": "string", "description": "Browser channel, e.g. msedge/chrome"},
                    },
                },
            },
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        if not params.get("url") and not params.get("actions") and not params.get("script"):
            return ["Provide at least one of: url, actions, or script"]
        return []

    async def execute(
        self,
        url: str | None = None,
        actions: list[dict[str, Any]] | None = None,
        script: dict[str, Any] | None = None,
        timeout: int | None = None,
        headless: bool | None = None,
        channel: str | None = None,
    ) -> str:
        payload = dict(script or {})
        if url:
            payload.setdefault("url", url)
        if actions is not None:
            payload["actions"] = actions
        payload["timeout"] = int(timeout or payload.get("timeout") or self.timeout_seconds)
        payload["headless"] = bool(self.headless if headless is None else headless)
        payload["channel"] = (channel or payload.get("channel") or self.channel or "").strip()

        if self.backend == "openclaw":
            return await self._run_openclaw(payload)
        return await self._run_native(payload)

    async def _run_openclaw(self, payload: dict[str, Any]) -> str:
        if not AIOHTTP_AVAILABLE:
            return "Error: aiohttp is required for OpenClaw Playwright backend"

        endpoint = f"{self.openclaw_gateway_url}/tools/invoke"
        headers = {"Content-Type": "application/json"}
        if self.openclaw_token:
            headers["Authorization"] = f"Bearer {self.openclaw_token}"

        args: dict[str, Any] = {
            "script": payload,
            "host": self.openclaw_host,
            "security": self.openclaw_security,
            "ask": self.openclaw_ask,
            "elevated": self.openclaw_elevated,
        }
        if self.openclaw_node:
            args["node"] = self.openclaw_node

        req = {
            "tool": self.openclaw_tool,
            "args": args,
            "sessionKey": self.openclaw_session_key,
        }
        try:
            timeout = aiohttp.ClientTimeout(total=max(10, int(payload.get("timeout", self.timeout_seconds)) + 10))
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(endpoint, headers=headers, json=req) as resp:
                    data = await resp.json(content_type=None)
                    if resp.status != 200:
                        return f"Error: OpenClaw Playwright invoke failed (HTTP {resp.status}): {data}"
                    if isinstance(data, dict) and data.get("ok") is False:
                        return f"Error: OpenClaw Playwright error: {data.get('error')}"
                    result = data.get("result") if isinstance(data, dict) else data
                    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            return f"Error: OpenClaw Playwright request failed: {exc}"

    async def _run_native(self, payload: dict[str, Any]) -> str:
        try:
            from playwright.async_api import async_playwright
        except Exception:
            return "Error: playwright is not installed. Run `playwright install` after installing package."

        timeout_ms = max(1000, int(payload.get("timeout", self.timeout_seconds) * 1000))
        headless = bool(payload.get("headless", self.headless))
        actions = payload.get("actions") or []
        if payload.get("url"):
            actions = [{"action": "navigate", "url": payload["url"]}] + list(actions)

        artifacts: list[str] = []
        step_results: list[dict[str, Any]] = []
        screenshot_root = self.workspace / self.screenshot_dir
        screenshot_root.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            browser = None
            launch_errors: list[str] = []
            preferred = (str(payload.get("channel") or "")).strip().lower()
            candidates = [c for c in [preferred, "msedge", "chrome", ""] if c is not None]
            seen: set[str] = set()
            for c in candidates:
                if c in seen:
                    continue
                seen.add(c)
                try:
                    if c:
                        browser = await p.chromium.launch(headless=headless, channel=c)
                    else:
                        browser = await p.chromium.launch(headless=headless)
                    break
                except Exception as exc:
                    launch_errors.append(f"{c or 'bundled-chromium'}: {exc}")
            if browser is None:
                return "Error: failed to launch browser. " + " | ".join(launch_errors)
            context = await browser.new_context()
            page = await context.new_page()
            page.set_default_timeout(timeout_ms)

            try:
                for idx, item in enumerate(actions):
                    action = str(item.get("action", "")).strip().lower()
                    if not action:
                        continue
                    step = {"index": idx, "action": action, "ok": True}

                    if action == "navigate":
                        url = str(item.get("url", "")).strip()
                        await page.goto(url, wait_until="domcontentloaded")
                        step["url"] = page.url
                    elif action == "click":
                        await page.click(str(item.get("selector", "")))
                    elif action == "click_any":
                        selectors = [str(s) for s in (item.get("selectors") or []) if str(s).strip()]
                        clicked = False
                        for selector in selectors:
                            locator = page.locator(selector).first
                            if await locator.count() > 0:
                                await locator.click()
                                clicked = True
                                break
                        if not clicked:
                            raise RuntimeError(f"click_any failed, no selector matched: {selectors}")
                    elif action == "fill":
                        await page.fill(str(item.get("selector", "")), str(item.get("text", "")))
                    elif action == "fill_any":
                        selectors = [str(s) for s in (item.get("selectors") or []) if str(s).strip()]
                        filled = False
                        for selector in selectors:
                            locator = page.locator(selector).first
                            if await locator.count() > 0:
                                await locator.fill(str(item.get("text", "")))
                                filled = True
                                break
                        if not filled:
                            raise RuntimeError(f"fill_any failed, no selector matched: {selectors}")
                    elif action == "press":
                        await page.press(str(item.get("selector", "")), str(item.get("key", "Enter")))
                    elif action == "press_any":
                        selectors = [str(s) for s in (item.get("selectors") or []) if str(s).strip()]
                        pressed = False
                        for selector in selectors:
                            locator = page.locator(selector).first
                            if await locator.count() > 0:
                                await locator.press(str(item.get("key", "Enter")))
                                pressed = True
                                break
                        if not pressed:
                            raise RuntimeError(f"press_any failed, no selector matched: {selectors}")
                    elif action == "wait":
                        if item.get("selector"):
                            await page.wait_for_selector(str(item.get("selector")))
                        else:
                            await page.wait_for_timeout(int(item.get("ms", 1000)))
                    elif action == "screenshot":
                        filename = str(item.get("path") or f"screenshot_{idx}.png")
                        path = screenshot_root / filename
                        await page.screenshot(path=str(path), full_page=bool(item.get("full_page", True)))
                        artifacts.append(str(path))
                        step["path"] = str(path)
                    elif action == "content":
                        html = await page.content()
                        step["result"] = html[:4000]
                    elif action == "title":
                        step["result"] = await page.title()
                    elif action == "extract_text":
                        selector = str(item.get("selector", "body"))
                        text = await page.text_content(selector)
                        step["result"] = (text or "")[:4000]
                    else:
                        step["ok"] = False
                        step["error"] = f"unsupported action: {action}"
                    step_results.append(step)
            finally:
                await context.close()
                await browser.close()

        return json.dumps(
            {"ok": True, "headless": headless, "steps": step_results, "artifacts": artifacts},
            ensure_ascii=False,
        )
