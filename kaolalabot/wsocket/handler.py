"""WebSocket handler - OpenClaw-style Gateway RPC over Socket.IO."""

import uuid
import asyncio
from typing import Dict, Set

from loguru import logger
import socketio

from kaolalabot import server_config
from kaolalabot.bus.events import OutboundMessage
from kaolalabot.gateway import get_rpc_protocol, get_gateway_auth
from kaolalabot.gateway.remote import get_remote_manager


class GatewayNamespace(socketio.AsyncNamespace):
    """
    Socket.IO namespace for Gateway RPC - OpenClaw style.
    
    Provides:
    - Unified RPC protocol (chat.send, chat.history, etc.)
    - Authentication
    - Remote access support
    """
    
    def __init__(self, namespace: str = "/gateway"):
        super().__init__(namespace)
        self.sessions: Dict[str, Set[str]] = {}
        self.authenticated_sessions: Dict[str, bool] = {}
        self._rpc = get_rpc_protocol()
        self._auth = get_gateway_auth()
        self._remote = get_remote_manager()
    
    async def connect(self, sid, environ, auth_data):
        """Handle client connection with authentication."""
        client_ip = environ.get("REMOTE_ADDR", environ.get("HTTP_X_FORWARDED_FOR", "unknown"))
        logger.info(f"Client connected: {sid} from {client_ip}")
        
        self.sessions[sid] = set()
        
        token = auth_data.get("token") if isinstance(auth_data, dict) else None
        password = auth_data.get("password") if isinstance(auth_data, dict) else None

        headers = {}
        auth_header = environ.get("HTTP_AUTHORIZATION")
        if auth_header:
            headers["authorization"] = auth_header

        auth_result = self._auth.authenticate_websocket(
            token=token,
            password=password,
            headers=headers,
            remote_addr=client_ip,
        )
        
        if self._auth.is_enabled and not auth_result.success:
            logger.warning(f"Authentication failed for {sid}: {auth_result.error}")
            await self.emit("error", {
                "code": "AUTH_FAILED",
                "message": auth_result.error,
            }, room=sid)
            await self.disconnect(sid)
            return
        
        self.authenticated_sessions[sid] = auth_result.success
        
        await self.emit("connected", {
            "sid": sid,
            "auth": auth_result.success,
            "userId": auth_result.user_id,
        }, room=sid)
    
    async def disconnect(self, sid):
        """Handle client disconnection."""
        logger.info(f"Client disconnected: {sid}")
        if sid in self.sessions:
            del self.sessions[sid]
        if sid in self.authenticated_sessions:
            del self.authenticated_sessions[sid]
    
    async def _event_broadcaster(self):
        """Broadcast events to connected clients."""
        pass
    
    async def on_rpc(self, sid, data):
        """
        Handle RPC request - OpenClaw style.
        
        Format: {"method": "chat.send", "data": {...}}
        Response: {"id": request_id, "result": {...}} or {"id": request_id, "error": {...}}
        """
        if not self.authenticated_sessions.get(sid) and self._auth.is_enabled:
            await self.emit("error", {
                "code": "NOT_AUTHENTICATED",
                "message": "Authentication required",
            }, room=sid)
            return
        
        request_id = data.get("id", str(uuid.uuid4()))
        method = data.get("method")
        params = data.get("data", {})
        
        if not method:
            await self.emit("response", {
                "id": request_id,
                "error": {"code": "INVALID_REQUEST", "message": "method required"},
            }, room=sid)
            return
        
        logger.info(f"RPC request: {method} from {sid}")
        
        result = await self._rpc.handle_request(method, params)
        
        await self.emit("response", {
            "id": request_id,
            "result": result,
        }, room=sid)
    
    async def on_chat_send(self, sid, data):
        """
        Handle chat.send request - OpenClaw style shortcut.
        
        Compatible with OpenClaw protocol.
        """
        if not self.authenticated_sessions.get(sid) and self._auth.is_enabled:
            await self.emit("error", {
                "code": "NOT_AUTHENTICATED",
                "message": "Authentication required",
            }, room=sid)
            return
        
        request_id = data.get("id", str(uuid.uuid4()))
        method = "chat.send"
        
        logger.info(f"chat.send request from {sid}")
        
        result = await self._rpc.handle_request(method, data)
        
        await self.emit("chat:response", {
            "id": request_id,
            "runId": result.get("runId"),
            "sessionKey": result.get("sessionKey"),
        }, room=sid)
    
    async def on_chat_history(self, sid, data):
        """Handle chat.history request."""
        if not self.authenticated_sessions.get(sid) and self._auth.is_enabled:
            await self.emit("error", {
                "code": "NOT_AUTHENTICATED",
                "message": "Authentication required",
            }, room=sid)
            return
        
        request_id = data.get("id", str(uuid.uuid4()))
        method = "chat.history"
        
        result = await self._rpc.handle_request(method, data)
        
        await self.emit("chat:history", {
            "id": request_id,
            "messages": result.get("messages", []),
            "hasMore": result.get("hasMore", False),
        }, room=sid)
    
    async def on_sessions_list(self, sid, data):
        """Handle sessions.list request."""
        if not self.authenticated_sessions.get(sid) and self._auth.is_enabled:
            await self.emit("error", {
                "code": "NOT_AUTHENTICATED",
                "message": "Authentication required",
            }, room=sid)
            return
        
        method = "sessions.list"
        result = await self._rpc.handle_request(method, data or {})
        
        await self.emit("sessions:list", result, room=sid)
    
    async def on_channels_status(self, sid, data):
        """Handle channels.status request."""
        if not self.authenticated_sessions.get(sid) and self._auth.is_enabled:
            await self.emit("error", {
                "code": "NOT_AUTHENTICATED",
                "message": "Authentication required",
            }, room=sid)
            return
        
        method = "channels.status"
        result = await self._rpc.handle_request(method, data or {})
        
        await self.emit("channels:status", result, room=sid)
    
    async def on_agents_list(self, sid, data):
        """Handle agents.list request."""
        if not self.authenticated_sessions.get(sid) and self._auth.is_enabled:
            await self.emit("error", {
                "code": "NOT_AUTHENTICATED",
                "message": "Authentication required",
            }, room=sid)
            return
        
        method = "agents.list"
        result = await self._rpc.handle_request(method, data or {})
        
        await self.emit("agents:list", result, room=sid)


class LegacyAgentNamespace(socketio.AsyncNamespace):
    """
    Legacy agent namespace for backward compatibility.
    Provides the original chat functionality.
    """
    
    def __init__(self, namespace: str = "/agent"):
        super().__init__(namespace)
        self.sessions: Dict[str, Set[str]] = {}
        self.active_agents: Dict[str, str] = {}
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self._web_sender_registered = False
    
    async def connect(self, sid, environ, auth):
        """Handle client connection."""
        logger.info(f"Legacy client connected: {sid}")
        self.sessions[sid] = set()
        await self.emit("connected", {"sid": sid}, room=sid)
        await self._ensure_web_sender()

    async def _ensure_web_sender(self) -> None:
        """Ensure the web channel routes outbound messages back into this namespace."""
        if self._web_sender_registered:
            return
        from kaolalabot.server import channel_manager
        if channel_manager is None:
            return
        web_channel = channel_manager.get_channel("web")
        if web_channel is None:
            return
        if not hasattr(web_channel, "set_sender"):
            return
        web_channel.set_sender(self._deliver_web_message)
        self._web_sender_registered = True

    async def _deliver_web_message(self, msg: OutboundMessage) -> None:
        """Deliver outbound bus messages for web sessions."""
        session_id = (
            msg.metadata.get("session_id")
            if msg.metadata
            else None
        ) or msg.chat_id

        if not session_id:
            return

        if msg.metadata.get("_progress") if msg.metadata else False:
            session_sids = [sid for sid, sess in self.sessions.items() if session_id in sess]
            for sid in session_sids:
                await self.emit(
                    "chat:progress",
                    {
                        "content": msg.content,
                        "session_id": session_id,
                        "tool_hint": bool(msg.metadata.get("_tool_hint")),
                    },
                    room=sid,
                )
            return

        pending = self._pending_responses.pop(session_id, None)
        if pending and not pending.done():
            pending.set_result(msg.content)
            return

        session_sids = [sid for sid, sess in self.sessions.items() if session_id in sess]
        for sid in session_sids:
            await self.emit(
                "chat:message",
                {
                    "content": msg.content,
                    "session_id": session_id,
                },
                room=sid,
            )
    
    async def disconnect(self, sid):
        """Handle client disconnection."""
        logger.info(f"Legacy client disconnected: {sid}")
        if sid in self.sessions:
            del self.sessions[sid]
        if sid in self.active_agents:
            del self.active_agents[sid]
    
    async def on_chat_start(self, sid, data):
        """Handle chat start event - integrates with MessageBus."""
        message = data.get("message", "")
        session_id = data.get("sessionId", str(uuid.uuid4()))
        
        logger.info(f"Chat started: session={session_id}, message={message[:50]}...")
        
        self.active_agents[sid] = session_id
        self.sessions[sid].add(session_id)
        
        await self.process_message_via_bus(sid, message, session_id)
    
    async def process_message_via_bus(self, sid, message: str, session_id: str):
        """Process message via MessageBus for channel integration."""
        from kaolalabot.bus.events import InboundMessage
        from kaolalabot.server import message_bus

        await self._ensure_web_sender()
        if message_bus:
            inbound_msg = InboundMessage(
                channel="web",
                sender_id=sid,
                chat_id=session_id,
                content=message,
                session_key_override=session_id,
            )
            await message_bus.publish_inbound(inbound_msg)
        
        response = await self._wait_for_response(session_id, message)
        
        await self.emit("chat:message", {
            "content": response,
            "session_id": session_id,
        }, room=sid)
    
    async def _wait_for_response(self, session_id: str, message: str, timeout: float = 60.0) -> str:
        """Wait for response from MessageBus outbound queue."""
        from kaolalabot.server import message_bus
        
        if not message_bus:
            return await self._process_direct(None, message, session_id)
        
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_responses[session_id] = future
        
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            self._pending_responses.pop(session_id, None)
            logger.warning("Timed out waiting bus response for session {}", session_id)
            return "Request timed out while waiting for assistant response."
    
    async def _process_direct(self, sid, message: str, session_id: str):
        """Fallback: Process message directly without MessageBus."""
        from kaolalabot.agent.cot.engine import CoTEngine
        from kaolalabot.memory.manager import MemoryManager
        from kaolalabot.providers.litellm_provider import LiteLLMProvider
        from kaolalabot.config.loader import load_config
        from kaolalabot.agent.tools.registry import ToolRegistry
        
        try:
            config = load_config()
            provider = LiteLLMProvider(
                api_key=config.get_api_key(),
                api_base=config.get_api_base(),
                default_model=server_config.settings.llm_model,
            )
            
            memory = MemoryManager(
                workspace=server_config.settings.workspace_path_expanded,
                working_capacity=server_config.settings.memory_working_capacity,
            )
            
            cot = CoTEngine(
                llm_provider=provider,
                tools=ToolRegistry(),
                max_iterations=server_config.settings.cot_max_iterations,
                enable_reflection=server_config.settings.cot_enable_reflection,
            )
            
            context = await memory.recall(message, session_id)
            
            thinking_id = str(uuid.uuid4())
            
            async for step in cot.think(message, context, session_id):
                step_data = {
                    "id": step.id,
                    "phase": step.phase.value,
                    "content": step.content,
                    "reasoning": step.reasoning,
                    "confidence": step.confidence,
                    "tool_used": step.tool_used,
                    "result": step.result,
                    "thinking_id": thinking_id,
                }
                if sid:
                    await self.emit("thinking:step", step_data, room=sid)
                    await self.emit("memory:updated", {"session_id": session_id}, room=sid)
            
            final_response = await cot.generate_response(message, context)
            
            await memory.add(
                content=f"User: {message}\nAssistant: {final_response}",
                memory_level="episodic",
                session_id=session_id,
            )
            
            response_data = {
                "content": final_response,
                "session_id": session_id,
                "thinking_id": thinking_id,
            }
            if sid:
                await self.emit("chat:message", response_data, room=sid)
                await self.emit("memory:updated", {"session_id": session_id}, room=sid)
            
            return final_response
            
        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            if sid:
                await self.emit("error", {
                    "code": "processing_error",
                    "message": str(e)
                }, room=sid)
            return f"Error: {str(e)}"


def register_handlers(sio_server: socketio.AsyncServer):
    """Register socket event handlers."""
    gateway_namespace = GatewayNamespace("/gateway")
    sio_server.register_namespace(gateway_namespace)
    
    legacy_namespace = LegacyAgentNamespace("/agent")
    sio_server.register_namespace(legacy_namespace)
    
    logger.info("Gateway RPC handlers registered (OpenClaw style)")


sio = None
