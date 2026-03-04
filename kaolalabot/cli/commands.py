"""kaolalabot CLI 命令模块"""

import asyncio
import os
import signal
import sys
from pathlib import Path

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from kaolalabot import __logo__, __version__
from kaolalabot.config.schema import Config
from kaolalabot.utils.helpers import sync_workspace_templates

app = typer.Typer(
    name="kaolalabot",
    help=f"{__logo__} kaolalabot - 个人AI助手",
    no_args_is_help=True,
)

console = Console()

# 考拉吉祥物 ASCII 艺术
KOALA_MASCOT = """
    ╭◜◝ ͡ ◜◝ ͡ ◜◝╮
    (  ˃̶͈◡˂ ̶͈ )  技术探索可以慢慢来
     ╰◟◞ ͜ ◟◞ ͜ ◟◞╯   不必焦虑～
      ╰━━━━━━━━━╯
"""

EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit", ":q", "退出", "再见"}

_PROMPT_SESSION: PromptSession | None = None
_SAVED_TERM_ATTRS = None


def _restore_terminal() -> None:
    """Restore terminal to its original state."""
    if _SAVED_TERM_ATTRS is None:
        return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _SAVED_TERM_ATTRS)
    except Exception:
        pass


def _init_prompt_session() -> None:
    """Create the prompt_toolkit session with persistent file history."""
    global _PROMPT_SESSION, _SAVED_TERM_ATTRS

    try:
        import termios
        _SAVED_TERM_ATTRS = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

    history_file = Path.home() / ".kaolalabot" / "history" / "cli_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    _PROMPT_SESSION = PromptSession(
        history=FileHistory(str(history_file)),
        enable_open_in_editor=False,
        multiline=False,
    )


def _print_agent_response(response: str, render_markdown: bool) -> None:
    """Render assistant response with consistent terminal styling."""
    content = response or ""
    body = Markdown(content) if render_markdown else Text(content)
    console.print()
    console.print(f"[cyan]{__logo__} kaolalabot[/cyan]")
    console.print(body)
    console.print()


def _is_exit_command(command: str) -> bool:
    """Return True when input should end interactive chat."""
    return command.lower() in EXIT_COMMANDS


async def _read_interactive_input_async() -> str:
    """Read user input using prompt_toolkit."""
    if _PROMPT_SESSION is None:
        raise RuntimeError("Call _init_prompt_session() first")
    try:
        with patch_stdout():
            return await _PROMPT_SESSION.prompt_async(
                HTML("<b fg='ansiblue'>你:</b> "),
            )
    except EOFError as exc:
        raise KeyboardInterrupt from exc


def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} kaolalabot v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """kaolalabot - Personal AI Assistant."""
    pass


@app.command()
def onboard():
    """初始化 kaolalabot 配置和工作区（中文交互界面）"""
    from kaolalabot.config.loader import get_config_path, load_config, save_config
    from kaolalabot.utils.helpers import get_workspace_path

    console.print("\n[bold cyan]🐨 欢迎使用 kaolalabot 初始化向导[/bold cyan]")
    console.print(KOALA_MASCOT)
    console.print("[dim]技术探索可以慢慢来，不必焦虑～[/dim]\n")
    console.print("[dim]本向导将帮助您完成初始配置...[/dim]\n")

    config_path = get_config_path()
    config = None

    if config_path.exists():
        console.print(f"[yellow]⚠️  配置文件已存在: {config_path}[/yellow]")
        console.print("  [bold]1[/bold] - 重置为默认值（将丢失现有配置）")
        console.print("  [bold]2[/bold] - 保留现有配置，仅添加新字段")
        console.print("  [bold]3[/bold] - 退出")
        
        choice = typer.prompt("请选择 (1/2/3)", default="2")
        if choice == "1":
            config = Config()
            save_config(config)
            console.print(f"[green]✓[/green] 配置已重置为默认值")
        elif choice == "2":
            config = load_config()
            save_config(config)
            console.print(f"[green]✓[/green] 配置已更新")
        else:
            console.print("[yellow]退出初始化...[/yellow]")
            raise typer.Exit()
    else:
        config = Config()
        save_config(config)
        console.print(f"[green]✓[/green] 已创建配置文件: {config_path}")

    workspace = get_workspace_path()
    if not workspace.exists():
        workspace.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] 已创建工作区: {workspace}")
    else:
        console.print(f"[dim]工作区已存在: {workspace}[/dim]")

    sync_workspace_templates(workspace)

    console.print("\n[bold cyan]📋 步骤1: LLM模型配置[/bold cyan]")
    console.print("请选择您要使用的AI模型提供商:\n")
    console.print("  [bold]1[/bold] - OpenRouter (推荐，支持多种模型)")
    console.print("  [bold]2[/bold] - Anthropic (Claude系列)")
    console.print("  [bold]3[/bold] - OpenAI (GPT系列)")
    console.print("  [bold]4[/bold] - DeepSeek")
    console.print("  [bold]5[/bold] - 跳过，稍后手动配置")

    provider_choice = typer.prompt("请选择 (1/2/3/4/5)", default="1")

    provider_map = {
        "1": "openrouter",
        "2": "anthropic", 
        "3": "openai",
        "4": "deepseek",
    }

    if provider_choice in provider_map:
        provider_name = provider_map[provider_choice]
        config.agents.defaults.provider = provider_name

        console.print(f"\n[dim]已选择: {provider_name.upper()}[/dim]")

        api_key_prompt = "请输入您的API密钥"
        if provider_name == "openrouter":
            api_key_prompt = "请输入您的OpenRouter API密钥 (可在 https://openrouter.ai/keys 获取)"
            config.agents.defaults.model = typer.prompt(
                "请输入模型名称 (直接回车使用默认)",
                default="anthropic/claude-sonnet-4-5"
            )
        elif provider_name == "anthropic":
            api_key_prompt = "请输入您的Anthropic API密钥"
            config.agents.defaults.model = typer.prompt(
                "请输入模型名称 (直接回车使用默认)",
                default="claude-sonnet-4-20250514"
            )
        elif provider_name == "openai":
            api_key_prompt = "请输入您的OpenAI API密钥"
            config.agents.defaults.model = typer.prompt(
                "请输入模型名称 (直接回车使用默认)",
                default="gpt-4o"
            )
        elif provider_name == "deepseek":
            api_key_prompt = "请输入您的DeepSeek API密钥"
            config.agents.defaults.model = typer.prompt(
                "请输入模型名称 (直接回车使用默认)",
                default="deepseek-chat"
            )

        if provider_choice != "5":
            api_key = typer.prompt(api_key_prompt, hide_input=True)
            if hasattr(config.providers, provider_name):
                provider_obj = getattr(config.providers, provider_name)
                provider_obj.api_key = api_key
                console.print(f"[green]✓[/green] API密钥已保存")

        advanced = typer.confirm("\n是否配置高级选项？", default=False)
        if advanced:
            console.print("\n[dim]高级配置选项:[/dim]")
            config.agents.defaults.temperature = float(typer.prompt(
                "temperature (0.0-1.0，直接回车使用默认)",
                default=str(config.agents.defaults.temperature)
            ))
            config.agents.defaults.max_tokens = int(typer.prompt(
                "max_tokens (最大生成token数，直接回车使用默认)",
                default=str(config.agents.defaults.max_tokens)
            ))

    console.print("\n[bold cyan]📋 步骤2: 飞书渠道配置[/bold cyan]")
    console.print("飞书集成当前状态:\n")
    console.print(f"  - 已启用: {config.channels.feishu.enabled}")
    console.print(f"  - App ID: {config.channels.feishu.app_id[:15] if config.channels.feishu.app_id else '未配置'}...")

    feishu_setup = typer.confirm("是否配置飞书渠道？", default=config.channels.feishu.enabled)
    if feishu_setup:
        config.channels.feishu.enabled = True
        
        new_app_id = typer.prompt(
            "请输入飞书App ID (直接回车保持现有值)",
            default=config.channels.feishu.app_id or ""
        )
        if new_app_id:
            config.channels.feishu.app_id = new_app_id

        new_app_secret = ""
        if config.channels.feishu.app_secret:
            # 有现有值时先询问是否需要修改
            change_secret = typer.confirm("是否修改飞书App Secret？", default=False)
            if change_secret:
                new_app_secret = typer.prompt(
                    "请输入新的飞书App Secret",
                    hide_input=True
                )
                config.channels.feishu.app_secret = new_app_secret
        else:
            # 没有现有值时直接输入
            new_app_secret = typer.prompt(
                "请输入飞书App Secret",
                hide_input=True
            )
            if new_app_secret:
                config.channels.feishu.app_secret = new_app_secret

        allow_from = typer.prompt(
            "允许使用的好友ID (多个用逗号分隔，直接回车跳过)",
            default=",".join(config.channels.feishu.allow_from) if config.channels.feishu.allow_from else ""
        )
        config.channels.feishu.allow_from = [x.strip() for x in allow_from.split(",") if x.strip()]
        
        console.print(f"[green]✓[/green] 飞书渠道配置已更新")
    else:
        config.channels.feishu.enabled = False

    console.print("\n[bold cyan]📋 步骤3: Coding Plan配置 (可选)[/bold cyan]")
    console.print("Coding Plan功能用于增强代码任务的处理能力:\n")
    console.print("  - 自动规划: 在执行前先制定计划")
    console.print("  - 自动评审: 完成后自动检查代码质量")
    console.print("  - 包含测试: 自动生成单元测试")
    console.print("  - 设计模式: 应用SOLID、DRY等设计原则")

    coding_enabled = typer.confirm("是否启用Coding Plan功能？", default=config.coding_plan.enabled)
    config.coding_plan.enabled = coding_enabled

    if coding_enabled:
        config.coding_plan.auto_plan = typer.confirm("启用自动规划？", default=config.coding_plan.auto_plan)
        config.coding_plan.auto_review = typer.confirm("启用自动评审？", default=config.coding_plan.auto_review)
        config.coding_plan.include_tests = typer.confirm("自动生成测试？", default=config.coding_plan.include_tests)
        
        doc_level = typer.prompt(
            "文档级别 (minimal/basic/standard/comprehensive)",
            default=config.coding_plan.documentation_level
        )
        config.coding_plan.documentation_level = doc_level
        
        patterns = typer.prompt(
            "设计模式 (多个用逗号分隔，如 solid,dry,kiss)",
            default=",".join(config.coding_plan.design_patterns)
        )
        config.coding_plan.design_patterns = [x.strip() for x in patterns.split(",") if x.strip()]
        
        console.print(f"[green]✓[/green] Coding Plan配置已保存")

    save_config(config)

    console.print("\n[bold green]✨ 初始化完成！[/bold green]")
    console.print("\n[bold]后续步骤:[/bold]")
    console.print("  1. 启动网关: [cyan]kaolalabot gateway[/cyan]")
    console.print("  2. 交互聊天: [cyan]kaolalabot agent -m \"你好！\"[/cyan]")
    console.print("  3. 查看状态: [cyan]kaolalabot status[/cyan]")
    console.print(f"\n[dim]配置文件位置: {config_path}[/dim]")
    console.print(f"[dim]工作区位置: {workspace}[/dim]")


def _make_provider(config: Config, required: bool = True):
    """Create the appropriate LLM provider from config."""
    from kaolalabot.providers.provider_wrapper import create_fallback_provider

    model = config.agents.defaults.model
    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)

    from kaolalabot.providers.registry import find_by_name
    spec = find_by_name(provider_name)
    
    if required and not model.startswith("bedrock/") and not (p and p.api_key) and not (spec and spec.is_oauth):
        console.print("[red]Error: No API key configured.[/red]")
        console.print("Set one in ~/.kaolalabot/config.json under providers section")
        raise typer.Exit(1)

    return create_fallback_provider(config)


@app.command()
def gateway(
    port: int = typer.Option(18790, "--port", "-p", help="网关端口"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
    no_provider: bool = typer.Option(False, "--no-provider", help="不启动LLM提供商（用于测试通道）"),
):
    """启动kaolalabot网关服务"""
    from kaolalabot.agent.loop import AgentLoop
    from kaolalabot.agent.tools import create_default_tools
    from kaolalabot.agent.tools.playwright import PlaywrightTool
    from kaolalabot.bus.queue import MessageBus
    from kaolalabot.channels.manager import ChannelManager
    from kaolalabot.config.loader import load_config
    from kaolalabot.session.manager import SessionManager
    from kaolalabot.services.clawhub import ClawhubClient, ClawhubSkillService
    from kaolalabot.services.heartbeat import HeartbeatService
    from kaolalabot.services.openclaw_local import OpenClawLocalService
    from kaolalabot.services.runtime import RuntimeServices, set_runtime_services
    from kaolalabot.services.scheduler import SchedulerService, ScheduledTask

    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    console.print(f"{__logo__} 正在启动kaolalabot网关，端口: {port}...")

    config = load_config()
    sync_workspace_templates(config.workspace_path)
    bus = MessageBus()
    
    provider = None
    if not no_provider:
        try:
            provider = _make_provider(config)
        except SystemExit:
            if not no_provider:
                console.print("[yellow]警告: 未配置LLM提供商。正在以 --no-provider 模式启动。[/yellow]")
                no_provider = True
    
    session_manager = SessionManager(config.workspace_path)
    tools = create_default_tools(workspace=config.workspace_path, config=config.tools)

    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        reasoning_effort=config.agents.defaults.reasoning_effort,
        session_manager=session_manager,
        channels_config=config.channels,
        tool_registry=tools,
        tools_config=config.tools,
        rate_limit_config=config.rate_limit,
    )

    channels = ChannelManager(config, bus)
    runtime_services = RuntimeServices()
    set_runtime_services(runtime_services)

    if channels.enabled_channels:
        console.print(f"[green]✓[/green] 已启用通道: {', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]警告: 未启用任何通道[/yellow]")

    async def run():
        try:
            if config.scheduler.enabled:
                runtime_services.scheduler = SchedulerService(
                    storage_file=config.scheduler.storage_file,
                    log_file=config.scheduler.log_file,
                    tick_seconds=config.scheduler.tick_seconds,
                    max_concurrent_runs=config.scheduler.max_concurrent_runs,
                )

                async def _agent_message_runner(task: ScheduledTask) -> str:
                    content = str(task.payload.get("content") or task.payload.get("message") or "")
                    if not content:
                        return "skipped: empty content"
                    await agent.process_direct(
                        content=content,
                        session_key=f"scheduler:{task.task_id}",
                        channel="cli",
                        chat_id="scheduler",
                    )
                    return "agent message executed"

                runtime_services.scheduler.register_runner("agent_message", _agent_message_runner)

                playwright_tool = PlaywrightTool(
                    workspace=config.workspace_path,
                    backend=config.tools.playwright.backend,
                    timeout_seconds=config.tools.playwright.timeout_seconds,
                    headless=config.tools.playwright.headless,
                    screenshot_dir=config.tools.playwright.screenshot_dir,
                    openclaw_gateway_url=config.tools.playwright.openclaw_gateway_url,
                    openclaw_token=config.tools.playwright.openclaw_token,
                    openclaw_session_key=config.tools.playwright.openclaw_session_key,
                    openclaw_tool=config.tools.playwright.openclaw_tool,
                    openclaw_host=config.tools.playwright.openclaw_host,
                    openclaw_security=config.tools.playwright.openclaw_security,
                    openclaw_ask=config.tools.playwright.openclaw_ask,
                    openclaw_node=config.tools.playwright.openclaw_node,
                    openclaw_elevated=config.tools.playwright.openclaw_elevated,
                )

                async def _playwright_script_runner(task: ScheduledTask) -> str:
                    payload = task.payload or {}
                    return await playwright_tool.execute(
                        script=payload.get("script"),
                        url=payload.get("url"),
                        actions=payload.get("actions"),
                        timeout=payload.get("timeout"),
                        headless=payload.get("headless"),
                    )

                async def _heartbeat_runner(task: ScheduledTask) -> str:
                    if not runtime_services.heartbeat:
                        return "heartbeat service not enabled"
                    result = await runtime_services.heartbeat.send_once()
                    return "heartbeat sent" if result.get("ok") else f"heartbeat failed: {result.get('error')}"

                runtime_services.scheduler.register_runner("playwright_script", _playwright_script_runner)
                runtime_services.scheduler.register_runner("heartbeat_once", _heartbeat_runner)
                await runtime_services.scheduler.start()

            if config.heartbeat.enabled:
                runtime_services.heartbeat = HeartbeatService(
                    endpoint=config.heartbeat.endpoint,
                    interval_seconds=config.heartbeat.interval_seconds,
                    timeout_seconds=config.heartbeat.timeout_seconds,
                    max_failures_before_alert=config.heartbeat.max_failures_before_alert,
                    auto_restart_on_failure=config.heartbeat.auto_restart_on_failure,
                    include_resource_usage=config.heartbeat.include_resource_usage,
                    health_provider=lambda: {
                        "channels": channels.get_status(),
                        "bus": {"inbound_size": bus.inbound_size, "outbound_size": bus.outbound_size},
                    },
                )
                await runtime_services.heartbeat.start()

            if config.clawhub.enabled:
                client = (
                    ClawhubClient(config.clawhub.base_url, config.clawhub.api_token)
                    if config.clawhub.base_url
                    else None
                )
                runtime_services.clawhub = ClawhubSkillService(
                    skills_dir=config.clawhub.skills_dir,
                    metadata_file=config.clawhub.metadata_file,
                    client=client,
                    sync_interval_seconds=config.clawhub.sync_interval_seconds,
                )
                await runtime_services.clawhub.start()

            if config.openclaw.enabled:
                runtime_services.openclaw = OpenClawLocalService(
                    gateway_url=config.openclaw.gateway_url,
                    token=config.openclaw.token,
                    timeout_seconds=config.openclaw.timeout_seconds,
                    session_key=config.openclaw.session_key,
                )
                await runtime_services.openclaw.start()

            tasks = [channels.start_all()]
            mcp_channel = channels.get_channel("mcp")
            if mcp_channel and hasattr(mcp_channel, "service"):
                runtime_services.mcp = mcp_channel.service
            if provider is not None:
                tasks.append(agent.run())
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            console.print("\n????...")
        finally:
            agent.stop()
            if runtime_services.openclaw:
                await runtime_services.openclaw.stop()
            if runtime_services.clawhub:
                await runtime_services.clawhub.stop()
            if runtime_services.heartbeat:
                await runtime_services.heartbeat.stop()
            if runtime_services.scheduler:
                await runtime_services.scheduler.stop()
            await channels.stop_all()

    asyncio.run(run())


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="发送给Agent的消息"),
    session_id: str = typer.Option("cli:direct", "--session", "-s", help="会话ID"),
    markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="将助手输出渲染为Markdown格式"),
    logs: bool = typer.Option(False, "--logs/--no-logs", help="在聊天时显示kaolalabot运行时日志"),
):
    """直接与Agent交互"""
    from loguru import logger

    from kaolalabot.agent.loop import AgentLoop
    from kaolalabot.agent.tools import create_default_tools
    from kaolalabot.bus.queue import MessageBus
    from kaolalabot.config.loader import load_config

    config = load_config()
    sync_workspace_templates(config.workspace_path)

    bus = MessageBus()
    provider = _make_provider(config)
    tools = create_default_tools(workspace=config.workspace_path, config=config.tools)

    if logs:
        logger.enable("kaolalabot")
    else:
        logger.disable("kaolalabot")

    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        reasoning_effort=config.agents.defaults.reasoning_effort,
        channels_config=config.channels,
        tool_registry=tools,
        tools_config=config.tools,
        rate_limit_config=config.rate_limit,
    )

    def _thinking_ctx():
        if logs:
            from contextlib import nullcontext
            return nullcontext()
        return console.status("[dim]kaolalabot 正在思考...[/dim]", spinner="dots")

    async def _cli_progress(content: str, *, tool_hint: bool = False) -> None:
        ch = agent_loop.channels_config
        if ch and tool_hint and not ch.send_tool_hints:
            return
        if ch and not tool_hint and not ch.send_progress:
            return
        console.print(f"  [dim]↳ {content}[/dim]")

    if message:
        async def run_once():
            with _thinking_ctx():
                response = await agent_loop.process_direct(message, session_id, on_progress=_cli_progress)
            _print_agent_response(response, render_markdown=markdown)

        asyncio.run(run_once())
    else:
        from kaolalabot.bus.events import InboundMessage
        _init_prompt_session()
        console.print(f"{__logo__} 交互模式 (输入 [bold]exit[/bold]、[bold] 退出 [/bold] 或 [bold]Ctrl+C[/bold] 退出)\n")
        console.print(KOALA_MASCOT)
        console.print("[dim]技术探索可以慢慢来，不必焦虑～ 开始和考拉小助手聊天吧！[/dim]\n")

        if ":" in session_id:
            cli_channel, cli_chat_id = session_id.split(":", 1)
        else:
            cli_channel, cli_chat_id = "cli", session_id

        def _exit_on_sigint(signum, frame):
            _restore_terminal()
            console.print("\n再见!")
            os._exit(0)

        signal.signal(signal.SIGINT, _exit_on_sigint)

        async def run_interactive():
            bus_task = asyncio.create_task(agent_loop.run())
            turn_done = asyncio.Event()
            turn_done.set()
            turn_response: list[str] = []

            async def _consume_outbound():
                while True:
                    try:
                        msg = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
                        if msg.metadata.get("_progress"):
                            is_tool_hint = msg.metadata.get("_tool_hint", False)
                            ch = agent_loop.channels_config
                            if ch and is_tool_hint and not ch.send_tool_hints:
                                pass
                            elif ch and not is_tool_hint and not ch.send_progress:
                                pass
                            else:
                                console.print(f"  [dim]↳ {msg.content}[/dim]")
                        elif not turn_done.is_set():
                            if msg.content:
                                turn_response.append(msg.content)
                            turn_done.set()
                        elif msg.content:
                            console.print()
                            _print_agent_response(msg.content, render_markdown=markdown)
                    except asyncio.TimeoutError:
                        continue
                    except asyncio.CancelledError:
                        break

            outbound_task = asyncio.create_task(_consume_outbound())

            try:
                while True:
                    try:
                        user_input = await _read_interactive_input_async()
                        command = user_input.strip()
                        if not command:
                            continue

                        if _is_exit_command(command):
                            _restore_terminal()
                            console.print("\n再见!")
                            break

                        turn_done.clear()
                        turn_response.clear()

                        await bus.publish_inbound(InboundMessage(
                            channel=cli_channel,
                            sender_id="user",
                            chat_id=cli_chat_id,
                            content=user_input,
                        ))

                        with _thinking_ctx():
                            await turn_done.wait()

                        if turn_response:
                            _print_agent_response(turn_response[0], render_markdown=markdown)
                    except KeyboardInterrupt:
                        _restore_terminal()
                        console.print("\n再见!")
                        break
                    except EOFError:
                        _restore_terminal()
                        console.print("\n再见!")
                        break
            finally:
                agent_loop.stop()
                outbound_task.cancel()
                await asyncio.gather(bus_task, outbound_task, return_exceptions=True)

        asyncio.run(run_interactive())


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
def channels_status():
    """显示通道状态"""
    from kaolalabot.config.loader import load_config

    config = load_config()

    table = Table(title="通道状态")
    table.add_column("通道", style="cyan")
    table.add_column("已启用", style="green")
    table.add_column("配置", style="yellow")

    fs = config.channels.feishu
    fs_config = f"app_id: {fs.app_id[:10]}..." if fs.app_id else "[dim]未配置[/dim]"
    table.add_row(
        "Feishu",
        "✓" if fs.enabled else "✗",
        fs_config
    )

    console.print(table)


@app.command()
def status():
    """显示kaolalabot状态"""
    from kaolalabot.config.loader import get_config_path, load_config

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} kaolalabot 状态\n")

    console.print(f"配置文件: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"工作区: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")

    if config_path.exists():
        from kaolalabot.providers.registry import PROVIDERS

        console.print(f"模型: {config.agents.defaults.model}")

        for spec in PROVIDERS:
            p = getattr(config.providers, spec.name, None)
            if p is None:
                continue
            if spec.is_local:
                if p.api_base:
                    console.print(f"{spec.label}: [green]✓ {p.api_base}[/green]")
                else:
                    console.print(f"{spec.label}: [dim]未设置[/dim]")
            else:
                has_key = bool(p.api_key)
                status = "[green]✓[/green]" if has_key else "[dim]未设置[/dim]"
                console.print(f"{spec.label}: {status}")


if __name__ == "__main__":
    app()
