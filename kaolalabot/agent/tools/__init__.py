"""Agent tools - Tool registry and exports."""

from pathlib import Path

from kaolalabot.agent.tools.base import Tool
from kaolalabot.agent.tools.registry import ToolRegistry
from kaolalabot.agent.tools.web import WebSearchTool, WebFetchTool
from kaolalabot.agent.tools.file import WriteFileTool, ReadFileTool, ListFilesTool
from kaolalabot.agent.tools.exec import ExecTool, PowerShellTool
from kaolalabot.agent.tools.playwright import PlaywrightTool
from kaolalabot.agent.tools.kaola_browser import KaolaBrowserTool
from kaolalabot.agent.tools.openclaw_browser import OpenClawBrowserTool


def create_default_tools(workspace=None, config=None):
    """Create and register default tools."""
    workspace = workspace or Path("./workspace")

    exec_timeout = 60
    restrict_to_workspace = False
    native_deny_commands: list[str] = []
    exec_backend = "native"
    openclaw_gateway_url = "http://127.0.0.1:18789"
    openclaw_token = ""
    openclaw_session_key = "main"
    openclaw_host = "sandbox"
    openclaw_security = "allowlist"
    openclaw_ask = "on-miss"
    openclaw_node = ""
    openclaw_elevated = False
    playwright_enabled = True
    playwright_backend = "native"
    playwright_timeout_seconds = 30
    playwright_headless = True
    playwright_channel = "msedge"
    playwright_screenshot_dir = "workspace/artifacts/playwright"
    playwright_openclaw_gateway_url = "http://127.0.0.1:18789"
    playwright_openclaw_token = ""
    playwright_openclaw_session_key = "main"
    playwright_openclaw_tool = "playwright"
    playwright_openclaw_host = "sandbox"
    playwright_openclaw_security = "allowlist"
    playwright_openclaw_ask = "on-miss"
    playwright_openclaw_node = ""
    playwright_openclaw_elevated = False
    openclaw_browser_enabled = False
    openclaw_browser_gateway_url = "http://127.0.0.1:18789"
    openclaw_browser_token = ""
    openclaw_browser_session_key = "main"
    openclaw_browser_profile = "openclaw"
    openclaw_browser_target = "host"
    openclaw_browser_node = ""
    openclaw_browser_timeout_ms = 15000
    kaola_browser_enabled = True
    kaola_browser_headless = False
    kaola_browser_channel = "msedge"
    kaola_browser_timeout_ms = 45000
    if config:
        exec_timeout = getattr(config, 'exec', None)
        if exec_timeout:
            exec_backend = getattr(exec_timeout, "backend", exec_backend)
            openclaw_gateway_url = getattr(exec_timeout, "openclaw_gateway_url", openclaw_gateway_url)
            openclaw_token = getattr(exec_timeout, "openclaw_token", openclaw_token)
            openclaw_session_key = getattr(exec_timeout, "openclaw_session_key", openclaw_session_key)
            openclaw_host = getattr(exec_timeout, "openclaw_host", openclaw_host)
            openclaw_security = getattr(exec_timeout, "openclaw_security", openclaw_security)
            openclaw_ask = getattr(exec_timeout, "openclaw_ask", openclaw_ask)
            openclaw_node = getattr(exec_timeout, "openclaw_node", openclaw_node)
            openclaw_elevated = getattr(exec_timeout, "openclaw_elevated", openclaw_elevated)
            exec_timeout = getattr(exec_timeout, 'timeout', 60)
        playwright_cfg = getattr(config, "playwright", None)
        if playwright_cfg:
            playwright_enabled = getattr(playwright_cfg, "enabled", playwright_enabled)
            playwright_backend = getattr(playwright_cfg, "backend", playwright_backend)
            playwright_timeout_seconds = getattr(playwright_cfg, "timeout_seconds", playwright_timeout_seconds)
            playwright_headless = getattr(playwright_cfg, "headless", playwright_headless)
            playwright_channel = getattr(playwright_cfg, "channel", playwright_channel)
            playwright_screenshot_dir = getattr(playwright_cfg, "screenshot_dir", playwright_screenshot_dir)
            playwright_openclaw_gateway_url = getattr(
                playwright_cfg, "openclaw_gateway_url", playwright_openclaw_gateway_url
            )
            playwright_openclaw_token = getattr(playwright_cfg, "openclaw_token", playwright_openclaw_token)
            playwright_openclaw_session_key = getattr(
                playwright_cfg, "openclaw_session_key", playwright_openclaw_session_key
            )
            playwright_openclaw_tool = getattr(playwright_cfg, "openclaw_tool", playwright_openclaw_tool)
            playwright_openclaw_host = getattr(playwright_cfg, "openclaw_host", playwright_openclaw_host)
            playwright_openclaw_security = getattr(
                playwright_cfg, "openclaw_security", playwright_openclaw_security
            )
            playwright_openclaw_ask = getattr(playwright_cfg, "openclaw_ask", playwright_openclaw_ask)
            playwright_openclaw_node = getattr(playwright_cfg, "openclaw_node", playwright_openclaw_node)
            playwright_openclaw_elevated = getattr(
                playwright_cfg, "openclaw_elevated", playwright_openclaw_elevated
            )
        oc_browser_cfg = getattr(config, "openclaw_browser", None)
        if oc_browser_cfg:
            openclaw_browser_enabled = getattr(oc_browser_cfg, "enabled", openclaw_browser_enabled)
            openclaw_browser_gateway_url = getattr(
                oc_browser_cfg, "gateway_url", openclaw_browser_gateway_url
            )
            openclaw_browser_token = getattr(oc_browser_cfg, "token", openclaw_browser_token)
            openclaw_browser_session_key = getattr(
                oc_browser_cfg, "session_key", openclaw_browser_session_key
            )
            openclaw_browser_profile = getattr(oc_browser_cfg, "profile", openclaw_browser_profile)
            openclaw_browser_target = getattr(oc_browser_cfg, "target", openclaw_browser_target)
            openclaw_browser_node = getattr(oc_browser_cfg, "node", openclaw_browser_node)
            openclaw_browser_timeout_ms = getattr(oc_browser_cfg, "timeout_ms", openclaw_browser_timeout_ms)
        kb_cfg = getattr(config, "kaola_browser", None)
        if kb_cfg:
            kaola_browser_enabled = getattr(kb_cfg, "enabled", kaola_browser_enabled)
            kaola_browser_headless = getattr(kb_cfg, "headless", kaola_browser_headless)
            kaola_browser_channel = getattr(kb_cfg, "channel", kaola_browser_channel)
            kaola_browser_timeout_ms = getattr(kb_cfg, "timeout_ms", kaola_browser_timeout_ms)
        restrict_to_workspace = getattr(config, 'restrict_to_workspace', False)
        native_deny_commands = list(getattr(config, "native_deny_commands", []) or [])

    registry = ToolRegistry()

    registry.register(WebSearchTool())
    registry.register(WebFetchTool())
    registry.register(WriteFileTool(workspace=workspace))
    registry.register(ReadFileTool(workspace=workspace))
    registry.register(ListFilesTool(workspace=workspace))
    registry.register(ExecTool(
        workspace=workspace,
        timeout=exec_timeout,
        restrict_to_workspace=restrict_to_workspace,
        deny_commands=native_deny_commands,
        backend=exec_backend,
        openclaw_gateway_url=openclaw_gateway_url,
        openclaw_token=openclaw_token,
        openclaw_session_key=openclaw_session_key,
        openclaw_host=openclaw_host,
        openclaw_security=openclaw_security,
        openclaw_ask=openclaw_ask,
        openclaw_node=openclaw_node,
        openclaw_elevated=openclaw_elevated,
    ))
    registry.register(PowerShellTool(workspace=workspace, timeout=exec_timeout))
    if playwright_enabled:
        registry.register(
            PlaywrightTool(
                workspace=workspace,
                backend=playwright_backend,
                timeout_seconds=playwright_timeout_seconds,
                headless=playwright_headless,
                channel=playwright_channel,
                screenshot_dir=playwright_screenshot_dir,
                openclaw_gateway_url=playwright_openclaw_gateway_url,
                openclaw_token=playwright_openclaw_token,
                openclaw_session_key=playwright_openclaw_session_key,
                openclaw_tool=playwright_openclaw_tool,
                openclaw_host=playwright_openclaw_host,
                openclaw_security=playwright_openclaw_security,
                openclaw_ask=playwright_openclaw_ask,
                openclaw_node=playwright_openclaw_node,
                openclaw_elevated=playwright_openclaw_elevated,
            )
        )
    if kaola_browser_enabled:
        registry.register(
            KaolaBrowserTool(
                workspace=workspace,
                headless=kaola_browser_headless,
                channel=kaola_browser_channel,
                timeout_ms=kaola_browser_timeout_ms,
            )
        )
    if openclaw_browser_enabled:
        registry.register(
            OpenClawBrowserTool(
                gateway_url=openclaw_browser_gateway_url,
                token=openclaw_browser_token,
                session_key=openclaw_browser_session_key,
                profile=openclaw_browser_profile,
                target=openclaw_browser_target,
                node=openclaw_browser_node,
                timeout_ms=openclaw_browser_timeout_ms,
            )
        )

    return registry


__all__ = [
    "Tool",
    "ToolRegistry",
    "WebSearchTool",
    "WebFetchTool",
    "WriteFileTool",
    "ReadFileTool",
    "ListFilesTool",
    "ExecTool",
    "PowerShellTool",
    "PlaywrightTool",
    "KaolaBrowserTool",
    "OpenClawBrowserTool",
    "create_default_tools",
]
