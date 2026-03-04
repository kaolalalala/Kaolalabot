from kaolalabot.agent.native_commands import NativeCommandRouter


def test_route_launch_powershell_cn():
    router = NativeCommandRouter()
    plan = router.plan("帮我打开powershell")
    assert plan is not None
    assert plan.kind == "launch_app"
    assert plan.command == 'start "" powershell'


def test_route_launch_notepad_cn():
    router = NativeCommandRouter()
    plan = router.plan("打开记事本")
    assert plan is not None
    assert plan.kind == "launch_app"
    assert plan.command == 'start "" notepad'


def test_route_explicit_command():
    router = NativeCommandRouter()
    plan = router.plan("执行命令: dir")
    assert plan is not None
    assert plan.kind == "run_command"
    assert plan.command == "dir"


def test_route_non_command():
    router = NativeCommandRouter()
    assert router.plan("你今天怎么样") is None

