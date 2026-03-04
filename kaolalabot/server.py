"""Kaolalabot Enhanced API Server

FastAPI-based backend with WebSocket support for real-time agent interaction.
Integrates with MessageBus for channel communication.
OpenClaw-style Gateway system.
"""

import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
from loguru import logger

from kaolalabot.api import api_router
from kaolalabot.api.system_services import router as system_services_router
from kaolalabot.wsocket.handler import register_handlers
from kaolalabot import server_config
from kaolalabot.config.loader import load_config
from kaolalabot.bus.queue import MessageBus
from kaolalabot.channels.manager import ChannelManager
from kaolalabot.gateway import (
    get_gateway_auth,
    get_remote_manager,
    configure_remote_access,
    AuthMode,
    RemoteMode,
)
from kaolalabot.services.clawhub import ClawhubClient, ClawhubSkillService
from kaolalabot.services.heartbeat import HeartbeatService
from kaolalabot.services.openclaw_local import OpenClawLocalService
from kaolalabot.services.runtime import RuntimeServices, get_runtime_services, set_runtime_services
from kaolalabot.services.scheduler import SchedulerService, ScheduledTask

message_bus: MessageBus | None = None
channel_manager: ChannelManager | None = None


def _parse_cors_origins() -> list[str]:
    origins = [
        origin.strip()
        for origin in server_config.settings.cors_allowed_origins.split(",")
        if origin.strip()
    ]
    return origins or ["http://localhost:5173", "http://127.0.0.1:5173"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global message_bus, channel_manager
    
    logger.info("Starting Kaolalabot Enhanced API Server (Gateway Mode)...")
    logger.info(f"Workspace: {server_config.settings.workspace_path}")
    logger.info(f"Debug mode: {server_config.settings.debug}")
    
    auth = get_gateway_auth(
        mode=AuthMode(server_config.gateway_settings.auth_mode),
        token=server_config.gateway_settings.auth_token,
        password=server_config.gateway_settings.auth_password,
    )
    logger.info(f"Gateway auth mode: {auth.mode.value}, enabled: {auth.is_enabled}")
    
    configure_remote_access(
        mode=RemoteMode(server_config.gateway_settings.remote_mode),
        url=server_config.gateway_settings.remote_url,
        token=server_config.gateway_settings.remote_token,
        password=server_config.gateway_settings.remote_password,
    )
    remote = get_remote_manager()
    logger.info(f"Remote access mode: {remote.mode.value}, enabled: {remote.is_enabled}")
    
    message_bus = MessageBus()
    logger.info("MessageBus initialized")
    
    try:
        config = load_config()
        runtime_services = RuntimeServices()
        set_runtime_services(runtime_services)
        channel_manager = ChannelManager(config, message_bus)
        await channel_manager.start_all()
        logger.info("ChannelManager started")
        mcp_channel = channel_manager.get_channel("mcp")
        if mcp_channel and hasattr(mcp_channel, "service"):
            runtime_services.mcp = mcp_channel.service
        
        from kaolalabot.providers.litellm_provider import LiteLLMProvider
        from kaolalabot.providers.provider_wrapper import create_fallback_provider
        from kaolalabot.agent.loop import AgentLoop
        from kaolalabot.agent.tools import create_default_tools
        from kaolalabot.agent.tools.playwright import PlaywrightTool
        
        provider = create_fallback_provider(config)
        
        tools = create_default_tools(
            workspace=server_config.settings.workspace_path_expanded,
            config=config.tools
        )
        
        agent_loop = AgentLoop(
            bus=message_bus,
            provider=provider,
            workspace=server_config.settings.workspace_path_expanded,
            max_iterations=config.agents.defaults.max_tool_iterations,
            temperature=config.agents.defaults.temperature,
            max_tokens=config.agents.defaults.max_tokens,
            tool_registry=tools,
            tools_config=config.tools,
            rate_limit_config=config.rate_limit,
        )
        
        asyncio.create_task(agent_loop.run())
        logger.info("AgentLoop started")

        if config.scheduler.enabled:
            scheduler_service = SchedulerService(
                storage_file=config.scheduler.storage_file,
                log_file=config.scheduler.log_file,
                tick_seconds=config.scheduler.tick_seconds,
                max_concurrent_runs=config.scheduler.max_concurrent_runs,
            )

            async def _agent_message_runner(task: ScheduledTask) -> str:
                content = str(task.payload.get("content") or task.payload.get("message") or "")
                if not content:
                    return "skipped: empty content"
                await agent_loop.process_direct(
                    content=content,
                    session_key=f"scheduler:{task.task_id}",
                    channel="cli",
                    chat_id="scheduler",
                )
                return "agent message executed"

            scheduler_service.register_runner("agent_message", _agent_message_runner)

            playwright_tool = PlaywrightTool(
                workspace=server_config.settings.workspace_path_expanded,
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

            scheduler_service.register_runner("playwright_script", _playwright_script_runner)
            scheduler_service.register_runner("heartbeat_once", _heartbeat_runner)
            await scheduler_service.start()
            runtime_services.scheduler = scheduler_service
            logger.info("Scheduler service started")

        if config.heartbeat.enabled:
            heartbeat_service = HeartbeatService(
                endpoint=config.heartbeat.endpoint,
                interval_seconds=config.heartbeat.interval_seconds,
                timeout_seconds=config.heartbeat.timeout_seconds,
                max_failures_before_alert=config.heartbeat.max_failures_before_alert,
                auto_restart_on_failure=config.heartbeat.auto_restart_on_failure,
                include_resource_usage=config.heartbeat.include_resource_usage,
                health_provider=lambda: {
                    "channels": channel_manager.get_status() if channel_manager else {},
                    "bus": {
                        "inbound_size": message_bus.inbound_size if message_bus else 0,
                        "outbound_size": message_bus.outbound_size if message_bus else 0,
                    },
                },
            )
            await heartbeat_service.start()
            runtime_services.heartbeat = heartbeat_service
            logger.info("Heartbeat service started")

        if config.clawhub.enabled:
            client = (
                ClawhubClient(config.clawhub.base_url, config.clawhub.api_token)
                if config.clawhub.base_url
                else None
            )
            clawhub_service = ClawhubSkillService(
                skills_dir=config.clawhub.skills_dir,
                metadata_file=config.clawhub.metadata_file,
                client=client,
                sync_interval_seconds=config.clawhub.sync_interval_seconds,
            )
            await clawhub_service.start()
            runtime_services.clawhub = clawhub_service
            logger.info("Clawhub skill service started")

        if config.openclaw.enabled:
            openclaw_service = OpenClawLocalService(
                gateway_url=config.openclaw.gateway_url,
                token=config.openclaw.token,
                timeout_seconds=config.openclaw.timeout_seconds,
                session_key=config.openclaw.session_key,
            )
            await openclaw_service.start()
            runtime_services.openclaw = openclaw_service
            logger.info("OpenClaw local service started")
        
    except Exception as e:
        logger.warning(f"ChannelManager/AgentLoop initialization failed: {e}")
    
    yield
    
    logger.info("Shutting down Kaolalabot Enhanced API Server...")

    services = get_runtime_services()
    if services.openclaw:
        await services.openclaw.stop()
    if services.clawhub:
        await services.clawhub.stop()
    if services.heartbeat:
        await services.heartbeat.stop()
    if services.scheduler:
        await services.scheduler.stop()
    if channel_manager:
        await channel_manager.stop_all()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="Kaolalabot Enhanced API",
        description="AI Agent with CoT and Memory System",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    cors_origins = _parse_cors_origins()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.include_router(api_router, prefix="/api")
    app.include_router(system_services_router, prefix="/api")
    
    @app.get("/")
    async def root():
        return {
            "name": "Kaolalabot Enhanced API",
            "version": "1.0.0",
            "status": "running"
        }
    
    @app.get("/health")
    async def health():
        return {"status": "healthy"}
    
    return app


# 创建Socket.IO ASGI应用
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=_parse_cors_origins(),
    logger=server_config.settings.debug,
)

# 注册socket事件处理器
register_handlers(sio)

# 创建ASGI应用 - 将FastAPI和Socket.IO结合
asgi_app = socketio.ASGIApp(
    sio,
    other_asgi_app=create_app(),
    socketio_path='/socket.io'
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        asgi_app,
        host=server_config.settings.host,
        port=server_config.settings.port,
    )
