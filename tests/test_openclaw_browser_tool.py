from pathlib import Path

from kaolalabot.agent.tools import create_default_tools
from kaolalabot.config.schema import Config


def test_openclaw_browser_tool_registered_when_enabled():
    cfg = Config()
    cfg.tools.openclaw_browser.enabled = True
    registry = create_default_tools(workspace=Path("."), config=cfg.tools)
    assert registry.has("openclaw_browser")


def test_kaola_browser_tool_registered_by_default():
    cfg = Config()
    registry = create_default_tools(workspace=Path("."), config=cfg.tools)
    assert registry.has("kaola_browser")
