"""Deterministic native command routing for high-confidence local actions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote_plus


NativeActionKind = Literal["launch_app", "run_command", "browser_automation"]


@dataclass(slots=True)
class NativeCommandPlan:
    """Executable native command plan."""

    kind: NativeActionKind
    command: str
    summary: str
    tool_name: str | None = None
    tool_args: dict | None = None


class NativeCommandRouter:
    """Match simple user requests into deterministic local command plans."""

    _OPEN_VERBS = (
        "open",
        "start",
        "launch",
        "run",
        "visit",
        "打开",
        "启动",
        "运行",
        "访问",
    )

    _APP_ALIASES: dict[str, tuple[str, ...]] = {
        "powershell": ("powershell", "pwsh", "power shell", "终端"),
        "notepad": ("notepad", "记事本"),
        "cmd": ("cmd", "command prompt", "命令提示符"),
        "explorer": ("explorer", "资源管理器", "文件管理器"),
        "chrome": ("chrome", "google chrome", "谷歌浏览器"),
        "msedge": ("edge", "msedge", "microsoft edge"),
    }

    _APP_COMMANDS: dict[str, str] = {
        "powershell": "start powershell",
        "notepad": 'start "" notepad',
        "cmd": "start cmd",
        "explorer": 'start "" explorer',
        "chrome": 'start "" chrome',
        "msedge": 'start "" msedge',
    }

    _APP_SUMMARY: dict[str, str] = {
        "powershell": "打开 PowerShell",
        "notepad": "打开记事本",
        "cmd": "打开命令提示符",
        "explorer": "打开资源管理器",
        "chrome": "打开 Chrome 浏览器",
        "msedge": "打开 Edge 浏览器",
    }

    _EXPLICIT_COMMAND_PATTERNS = (
        re.compile(r"^\s*(?:请)?(?:帮我)?(?:直接)?(?:执行|运行)(?:命令)?\s*[:：]\s*(.+?)\s*$", re.IGNORECASE),
        re.compile(r"^\s*(?:cmd|shell|powershell)\s*[:：]\s*(.+?)\s*$", re.IGNORECASE),
        re.compile(r"^\s*run\s+command\s*[:：]\s*(.+?)\s*$", re.IGNORECASE),
    )

    _DIRECT_COMMAND_PREFIXES = (
        "start ",
        "dir",
        "ls",
        "cd ",
        "mkdir ",
        "copy ",
        "cp ",
        "del ",
        "rm ",
        "python ",
        "node ",
        "java ",
        "git ",
        "powershell ",
        "cmd ",
        "get-",
        "set-",
        "test-",
        "start-",
        "stop-",
        ".\\",
        "./",
    )

    _URL_RE = re.compile(r"(?i)\b((?:https?://|www\.)[^\s`]+)")
    _BROWSER_SEARCH_CN_RE = re.compile(
        r"(?is)在(?:谷歌|google|chrome|浏览器).{0,40}?搜索\s*([^\n，。！？?]+)\s*(?:网页|网站)?"
        r".{0,80}?(?:并且|然后|并在|在该网页|在这个网页).{0,40}?搜索\s*([^\n，。！？?]+)"
    )
    _BROWSER_SEARCH_EN_RE = re.compile(
        r"(?is)(?:in|on)?\s*(?:google|chrome|browser).{0,60}?search\s+([a-z0-9 ._/-]+?)"
        r"(?:\s+site|\s+page|\s+website|)\s*(?:and then|then|and).{0,50}?search\s+([a-z0-9 ._/-]+)"
    )

    def plan(self, text: str) -> NativeCommandPlan | None:
        """Return deterministic command plan when message is clearly actionable."""
        message = self._normalize_text(text)
        if not message:
            return None

        explicit = self._match_explicit_command(message)
        if explicit:
            return explicit

        launch = self._match_launch_app(message)
        if launch:
            return launch

        open_url = self._match_open_url(message)
        if open_url:
            return open_url

        browser_flow = self._match_browser_search_workflow(message)
        if browser_flow:
            return browser_flow

        direct = self._match_direct_command(message)
        if direct:
            return direct

        return None

    @staticmethod
    def _normalize_text(text: str) -> str:
        value = (text or "").strip()
        if value.startswith("`") and value.endswith("`") and len(value) >= 2:
            value = value[1:-1].strip()
        if value.startswith("```") and value.endswith("```"):
            value = value[3:-3].strip()
        return value

    def _match_explicit_command(self, text: str) -> NativeCommandPlan | None:
        for pattern in self._EXPLICIT_COMMAND_PATTERNS:
            match = pattern.match(text)
            if not match:
                continue
            command = match.group(1).strip().strip("`")
            if command:
                return NativeCommandPlan(
                    kind="run_command",
                    command=command,
                    summary=f"执行命令: {command}",
                )
        return None

    def _match_launch_app(self, text: str) -> NativeCommandPlan | None:
        lower = text.lower()
        if not any(verb in lower or verb in text for verb in self._OPEN_VERBS):
            return None

        url = self._extract_url(text)
        for app, aliases in self._APP_ALIASES.items():
            if any(alias in lower or alias in text for alias in aliases):
                command = self._APP_COMMANDS[app]
                if url:
                    command = f'{command} "{url}"'
                return NativeCommandPlan(
                    kind="launch_app",
                    command=command,
                    summary=self._APP_SUMMARY[app],
                )
        return None

    def _match_direct_command(self, text: str) -> NativeCommandPlan | None:
        normalized = text.strip()
        lower = normalized.lower()
        if any(lower.startswith(prefix) for prefix in self._DIRECT_COMMAND_PREFIXES):
            return NativeCommandPlan(
                kind="run_command",
                command=normalized,
                summary=f"执行命令: {normalized}",
            )
        return None

    def _match_open_url(self, text: str) -> NativeCommandPlan | None:
        url = self._extract_url(text)
        if not url:
            return None
        lower = text.lower()
        if not any(verb in lower or verb in text for verb in self._OPEN_VERBS):
            return None
        return NativeCommandPlan(
            kind="run_command",
            command=f'start "" "{url}"',
            summary=f"打开网页: {url}",
        )

    def _extract_url(self, text: str) -> str | None:
        match = self._URL_RE.search(text)
        if not match:
            return None
        url = match.group(1).strip().rstrip("。.!?,，")
        if url.lower().startswith("www."):
            return f"https://{url}"
        return url

    def _match_browser_search_workflow(self, text: str) -> NativeCommandPlan | None:
        m = self._BROWSER_SEARCH_CN_RE.search(text)
        if not m:
            m = self._BROWSER_SEARCH_EN_RE.search(text)
        if not m:
            return None

        outer_query = m.group(1).strip()
        inner_query = m.group(2).strip().rstrip("。.!?,，")
        outer_query = re.sub(r"(网页|网站)$", "", outer_query, flags=re.IGNORECASE).strip()
        if not outer_query or not inner_query:
            return None

        target_url = self._resolve_site_url_from_query(outer_query)
        if target_url:
            actions = [
                {"action": "navigate", "url": target_url},
                {"action": "wait", "ms": 1200},
                {
                    "action": "fill_any",
                    "selectors": [
                        "input#query-builder-test",
                        "input[name='q']",
                        "input[aria-label='Search or jump to...']",
                    ],
                    "text": inner_query,
                },
                {
                    "action": "press_any",
                    "selectors": [
                        "input#query-builder-test",
                        "input[name='q']",
                        "input[aria-label='Search or jump to...']",
                    ],
                    "key": "Enter",
                },
                {"action": "wait", "ms": 1500},
                {"action": "title"},
            ]
        else:
            google_query = quote_plus(outer_query)
            actions = [
                {"action": "navigate", "url": f"https://www.google.com/search?q={google_query}"},
                {"action": "wait", "ms": 1500},
                {"action": "click_any", "selectors": ["#search a h3", "#search a"]},
                {"action": "wait", "ms": 1500},
                {"action": "fill", "selector": "input[name='q']", "text": inner_query},
                {"action": "press", "selector": "input[name='q']", "key": "Enter"},
                {"action": "wait", "ms": 1500},
                {"action": "title"},
            ]

        return NativeCommandPlan(
            kind="browser_automation",
            command="playwright",
            summary=f"浏览器自动化：搜索“{outer_query}”并在目标站内搜索“{inner_query}”",
            tool_name="playwright",
            tool_args={
                "workflow": {
                    "outer_query": outer_query,
                    "inner_query": inner_query,
                    "target_url": target_url,
                },
                "script": {"actions": actions, "headless": False, "timeout": 60},
            },
        )

    @staticmethod
    def _resolve_site_url_from_query(query: str) -> str | None:
        lower = query.lower()
        if "github" in lower:
            return "https://github.com"
        if "gitee" in lower:
            return "https://gitee.com"
        return None
