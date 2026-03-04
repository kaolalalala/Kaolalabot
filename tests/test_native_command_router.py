from kaolalabot.agent.native_commands import NativeCommandRouter


def test_router_launch_app_from_natural_language():
    router = NativeCommandRouter()
    plan = router.plan("请帮我打开powershell")
    assert plan is not None
    assert plan.kind == "launch_app"
    assert "powershell" in plan.command.lower()


def test_router_direct_start_command():
    router = NativeCommandRouter()
    plan = router.plan("start cmd")
    assert plan is not None
    assert plan.command.lower().startswith("start")
    assert "cmd" in plan.command.lower()


def test_router_supports_chrome_alias():
    router = NativeCommandRouter()
    plan = router.plan("打开chrome浏览器")
    assert plan is not None
    assert "chrome" in plan.command.lower()


def test_router_supports_backtick_command():
    router = NativeCommandRouter()
    plan = router.plan("`start powershell`")
    assert plan is not None
    assert "start" in plan.command.lower()


def test_router_open_browser_with_url():
    router = NativeCommandRouter()
    plan = router.plan("打开谷歌浏览器并访问 https://example.com")
    assert plan is not None
    assert "chrome" in plan.command.lower()
    assert "https://example.com" in plan.command.lower()


def test_router_open_url_with_default_browser():
    router = NativeCommandRouter()
    plan = router.plan("请打开 https://example.com/docs")
    assert plan is not None
    assert plan.command.lower().startswith("start ")
    assert "https://example.com/docs" in plan.command.lower()


def test_router_browser_search_workflow():
    router = NativeCommandRouter()
    plan = router.plan("在谷歌浏览器搜索github网页，并且在该网页里搜索agent reach项目")
    assert plan is not None
    assert plan.kind == "browser_automation"
    assert plan.tool_name == "playwright"
    assert isinstance(plan.tool_args, dict)
    actions = plan.tool_args.get("script", {}).get("actions", [])
    assert len(actions) >= 4
