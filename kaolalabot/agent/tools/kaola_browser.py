"""Kaolalabot dedicated browser automation tool with persistent profile."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from kaolalabot.agent.tools.base import Tool

try:
    from playwright.async_api import BrowserContext, Error as PlaywrightError, Page, async_playwright

    PLAYWRIGHT_AVAILABLE = True
except Exception:
    PLAYWRIGHT_AVAILABLE = False
    BrowserContext = Any  # type: ignore[assignment]
    Page = Any  # type: ignore[assignment]
    PlaywrightError = Exception  # type: ignore[assignment]


class _KaolaBrowserSession:
    """Process-local dedicated browser session."""

    def __init__(self, workspace: Path, headless: bool, channel: str, timeout_ms: int):
        self.workspace = workspace
        self.headless = headless
        self.channel = (channel or "").strip().lower()
        self.timeout_ms = max(2000, int(timeout_ms))
        self._pw = None
        self._context: BrowserContext | None = None
        self._lock = asyncio.Lock()

    async def _ensure_started(self) -> Page:
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("playwright is not installed")

        if self._context is None:
            profile_dir = self.workspace / "workspace" / "artifacts" / "kaola_browser" / "profile"
            profile_dir.mkdir(parents=True, exist_ok=True)
            self._pw = await async_playwright().start()
            ctx = None
            launch_errors: list[str] = []
            candidates = [c for c in [self.channel, "msedge", "chrome", ""] if c is not None]
            seen: set[str] = set()
            for c in candidates:
                if c in seen:
                    continue
                seen.add(c)
                try:
                    if c:
                        ctx = await self._pw.chromium.launch_persistent_context(
                            user_data_dir=str(profile_dir),
                            headless=self.headless,
                            channel=c,
                            viewport={"width": 1440, "height": 900},
                        )
                    else:
                        ctx = await self._pw.chromium.launch_persistent_context(
                            user_data_dir=str(profile_dir),
                            headless=self.headless,
                            viewport={"width": 1440, "height": 900},
                        )
                    break
                except Exception as exc:
                    launch_errors.append(f"{c or 'bundled-chromium'}: {exc}")
            if ctx is None:
                raise RuntimeError("failed to launch browser profile: " + " | ".join(launch_errors))
            self._context = ctx
            self._context.set_default_timeout(self.timeout_ms)

        page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        page.set_default_timeout(self.timeout_ms)
        return page

    async def _snapshot(self, page: Page, limit: int = 200, compact: bool = False) -> str:
        script = """
() => {
  const out = [];
  const nodes = Array.from(document.querySelectorAll('a,button,input,textarea,select,[role="button"],[contenteditable="true"]'));
  let idx = 1;
  for (const el of nodes) {
    const tag = (el.tagName || '').toLowerCase();
    const text = ((el.innerText || el.textContent || '').trim()).slice(0, 80);
    const placeholder = (el.getAttribute('placeholder') || '').slice(0, 60);
    const aria = (el.getAttribute('aria-label') || '').slice(0, 60);
    const type = (el.getAttribute('type') || '').toLowerCase();
    if (!text && !placeholder && !aria && tag !== 'input' && tag !== 'textarea') continue;
    const ref = 'e' + idx++;
    el.setAttribute('data-kaola-ref', ref);
    out.push({ ref, tag, text, placeholder, aria, type });
  }
  return { title: document.title || '', url: location.href, elements: out };
}
"""
        data = await page.evaluate(script)
        elements = list((data or {}).get("elements") or [])[: max(10, int(limit))]
        payload = {"title": (data or {}).get("title", ""), "url": (data or {}).get("url", ""), "elements": elements}
        if not compact:
            return json.dumps(payload, ensure_ascii=False)

        lines = [f"title: {payload['title']}", f"url: {payload['url']}"]
        for item in elements:
            label = item.get("text") or item.get("placeholder") or item.get("aria") or ""
            tag = item.get("tag") or "node"
            lines.append(f"{tag} [ref={item.get('ref')}] {label}".strip())
        return "\n".join(lines)

    async def _act(self, page: Page, request: dict[str, Any]) -> str:
        kind = str((request or {}).get("kind") or "").lower()
        ref = str((request or {}).get("ref") or "").strip()
        if not kind or not ref:
            return "Error: act requires request.kind and request.ref"
        locator = page.locator(f"[data-kaola-ref='{ref}']").first
        if await locator.count() == 0:
            return f"Error: ref not found: {ref}"
        if kind == "click":
            await locator.click()
            return '{"ok":true,"action":"click"}'
        if kind == "type":
            text = str((request or {}).get("text") or "")
            submit = bool((request or {}).get("submit"))
            try:
                await locator.fill(text)
            except Exception:
                # Some pages expose search entry as a button; click then type globally.
                await locator.click()
                await page.keyboard.type(text)
            if submit:
                try:
                    await locator.press("Enter")
                except Exception:
                    await page.keyboard.press("Enter")
            return '{"ok":true,"action":"type"}'
        if kind == "press":
            key = str((request or {}).get("key") or "Enter")
            await locator.press(key)
            return '{"ok":true,"action":"press"}'
        return f"Error: unsupported act kind: {kind}"

    async def run(self, action: str, **kwargs: Any) -> str:
        async with self._lock:
            try:
                page = await self._ensure_started()
                act = action.strip().lower()
                if act in {"status"}:
                    return json.dumps({"ok": True, "started": self._context is not None, "url": page.url}, ensure_ascii=False)
                if act in {"start"}:
                    return json.dumps({"ok": True, "started": True}, ensure_ascii=False)
                if act in {"open", "navigate"}:
                    target_url = str(kwargs.get("target_url") or "").strip()
                    if not target_url:
                        return "Error: target_url is required"
                    await page.goto(target_url, wait_until="domcontentloaded")
                    return json.dumps({"ok": True, "url": page.url, "title": await page.title()}, ensure_ascii=False)
                if act == "snapshot":
                    return await self._snapshot(
                        page,
                        limit=int(kwargs.get("limit") or 200),
                        compact=bool(kwargs.get("compact")),
                    )
                if act == "act":
                    req = kwargs.get("request") if isinstance(kwargs.get("request"), dict) else {}
                    return await self._act(page, req)
                if act == "tabs":
                    tabs = [{"index": i, "url": p.url, "title": await p.title()} for i, p in enumerate(self._context.pages)]
                    return json.dumps({"ok": True, "tabs": tabs}, ensure_ascii=False)
                if act == "stop":
                    await self.close()
                    return json.dumps({"ok": True, "stopped": True}, ensure_ascii=False)
                return f"Error: unsupported action: {action}"
            except PlaywrightError as exc:
                return f"Error: playwright browser failed: {exc}"
            except Exception as exc:
                return f"Error: kaola_browser failed: {exc}"

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._pw is not None:
            await self._pw.stop()
            self._pw = None


class KaolaBrowserTool(Tool):
    """Dedicated browser tool for kaolalabot."""

    def __init__(self, workspace: Path, headless: bool = False, channel: str = "msedge", timeout_ms: int = 45000):
        self._session = _KaolaBrowserSession(
            workspace=workspace,
            headless=headless,
            channel=channel,
            timeout_ms=timeout_ms,
        )

    @property
    def name(self) -> str:
        return "kaola_browser"

    @property
    def description(self) -> str:
        return (
            "Kaolalabot dedicated browser automation with persistent profile. "
            "Actions: status/start/open/navigate/snapshot/act/tabs/stop."
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
                        "action": {"type": "string"},
                        "target_url": {"type": "string"},
                        "request": {"type": "object"},
                        "compact": {"type": "boolean"},
                        "limit": {"type": "integer"},
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
        request: dict[str, Any] | None = None,
        compact: bool | None = None,
        limit: int | None = None,
        **_: Any,
    ) -> str:
        return await self._session.run(
            action=action,
            target_url=target_url,
            request=request or {},
            compact=bool(compact),
            limit=int(limit or 200),
        )
