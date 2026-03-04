"""Gateway RPC Protocol - OpenClaw style unified message protocol."""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Callable, Awaitable
from enum import Enum

from loguru import logger


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class ChatMessage:
    role: str
    content: str
    name: Optional[str] = None
    tool_calls: Optional[list] = None
    tool_call_id: Optional[str] = None
    thinking: Optional[str] = None
    
    def to_dict(self) -> dict:
        result = {"role": self.role, "content": self.content}
        if self.name:
            result["name"] = self.name
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        if self.thinking:
            result["thinking"] = self.thinking
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            name=data.get("name"),
            tool_calls=data.get("tool_calls"),
            tool_call_id=data.get("tool_call_id"),
            thinking=data.get("thinking"),
        )


@dataclass
class ChatHistoryItem:
    id: str
    role: str
    content: str
    timestamp: str
    name: Optional[str] = None
    thinking: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "name": self.name,
            "thinking": self.thinking,
        }
    
    @classmethod
    def from_message(cls, msg: ChatMessage, msg_id: str = None) -> "ChatHistoryItem":
        return cls(
            id=msg_id or str(uuid.uuid4()),
            role=msg.role,
            content=msg.content,
            timestamp=datetime.now().isoformat(),
            name=msg.name,
            thinking=msg.thinking,
        )


@dataclass
class ChatSendRequest:
    session_key: str
    message: str
    thinking: bool = True
    deliver: Optional[str] = None
    timeout_ms: int = 120000
    idempotency_key: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> "ChatSendRequest":
        return cls(
            session_key=data.get("sessionKey", "main"),
            message=data.get("message", ""),
            thinking=data.get("thinking", True),
            deliver=data.get("deliver"),
            timeout_ms=data.get("timeoutMs", 120000),
            idempotency_key=data.get("idempotencyKey"),
        )


@dataclass
class ChatHistoryRequest:
    session_key: str
    limit: int = 50
    
    @classmethod
    def from_dict(cls, data: dict) -> "ChatHistoryRequest":
        return cls(
            session_key=data.get("sessionKey", "main"),
            limit=data.get("limit", 50),
        )


@dataclass
class ChatHistoryResponse:
    session_key: str
    messages: list[dict]
    has_more: bool = False
    
    def to_dict(self) -> dict:
        return {
            "sessionKey": self.session_key,
            "messages": self.messages,
            "hasMore": self.has_more,
        }


@dataclass
class ChatSendResponse:
    run_id: str
    session_key: str
    
    def to_dict(self) -> dict:
        return {
            "runId": self.run_id,
            "sessionKey": self.session_key,
        }


@dataclass
class ChatInjectRequest:
    session_key: str
    role: str
    content: str
    name: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> "ChatInjectRequest":
        return cls(
            session_key=data.get("sessionKey", "main"),
            role=data.get("role", "assistant"),
            content=data.get("content", ""),
            name=data.get("name"),
        )


RPCMethod = Callable[..., Awaitable[dict]]


class GatewayRPCProtocol:
    """
    Gateway RPC Protocol Handler - OpenClaw style.
    
    Provides unified message protocol:
    - chat.send: Send message to agent
    - chat.history: Get session history
    - chat.inject: Inject message directly to transcript
    - sessions.list: List all sessions
    - sessions.patch: Patch session parameters
    """
    
    def __init__(self):
        self._handlers: dict[str, RPCMethod] = {}
        self._sessions: dict[str, list[ChatMessage]] = {}
        self._sessions_meta: dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        self._handlers = {
            "chat.send": self._handle_chat_send,
            "chat.history": self._handle_chat_history,
            "chat.inject": self._handle_chat_inject,
            "chat.abort": self._handle_chat_abort,
            "sessions.list": self._handle_sessions_list,
            "sessions.patch": self._handle_sessions_patch,
            "sessions.delete": self._handle_sessions_delete,
            "agents.list": self._handle_agents_list,
            "channels.status": self._handle_channels_status,
        }
    
    async def _handle_chat_send(self, data: dict) -> dict:
        request = ChatSendRequest.from_dict(data)
        
        async with self._lock:
            if request.session_key not in self._sessions:
                self._sessions[request.session_key] = []
                self._sessions_meta[request.session_key] = {
                    "created_at": datetime.now().isoformat(),
                    "message_count": 0,
                }
            
            user_msg = ChatMessage(role="user", content=request.message)
            self._sessions[request.session_key].append(user_msg)
            self._sessions_meta[request.session_key]["message_count"] += 1
        
        run_id = request.idempotency_key or str(uuid.uuid4())
        
        response_text = await self._process_message(
            session_key=request.session_key,
            message=request.message,
            run_id=run_id,
        )
        
        async with self._lock:
            assistant_msg = ChatMessage(role="assistant", content=response_text)
            self._sessions[request.session_key].append(assistant_msg)
            self._sessions_meta[request.session_key]["message_count"] += 1
        
        return ChatSendResponse(run_id=run_id, session_key=request.session_key).to_dict()
    
    async def _process_message(self, session_key: str, message: str, run_id: str) -> str:
        from kaolalabot.providers.litellm_provider import LiteLLMProvider
        from kaolalabot.config.loader import load_config
        from kaolalabot import server_config
        
        try:
            config = load_config()
            provider = LiteLLMProvider(
                api_key=config.get_api_key(),
                api_base=config.get_api_base(),
                default_model=server_config.settings.llm_model,
            )
            
            async with self._lock:
                history = self._sessions.get(session_key, [])[-10:]
            
            messages = [{"role": "system", "content": "You are a helpful AI assistant."}]
            for msg in history:
                messages.append({"role": msg.role, "content": msg.content})
            messages.append({"role": "user", "content": message})
            
            response = await provider.chat(messages)
            return response.content if response.content else "No response generated."
            
        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_chat_history(self, data: dict) -> dict:
        request = ChatHistoryRequest.from_dict(data)
        
        async with self._lock:
            messages = self._sessions.get(request.session_key, [])[-request.limit:]
        
        history_items = [
            ChatHistoryItem.from_message(msg).to_dict()
            for msg in messages
        ]
        
        return ChatHistoryResponse(
            session_key=request.session_key,
            messages=history_items,
            has_more=len(messages) >= request.limit,
        ).to_dict()
    
    async def _handle_chat_inject(self, data: dict) -> dict:
        request = ChatInjectRequest.from_dict(data)
        
        async with self._lock:
            if request.session_key not in self._sessions:
                self._sessions[request.session_key] = []
            
            msg = ChatMessage(role=request.role, content=request.content, name=request.name)
            self._sessions[request.session_key].append(msg)
        
        return {"success": True, "sessionKey": request.session_key}
    
    async def _handle_chat_abort(self, data: dict) -> dict:
        return {"success": True, "message": "Abort not implemented"}
    
    async def _handle_sessions_list(self, data: dict) -> dict:
        limit = data.get("limit", 20)
        active_minutes = data.get("activeMinutes", 30)
        
        async with self._lock:
            sessions = []
            now = datetime.now()
            for sid, meta in self._sessions_meta.items():
                created = datetime.fromisoformat(meta["created_at"])
                if (now - created).total_seconds() / 60 <= active_minutes:
                    last_msg = self._sessions.get(sid, [])[-1] if self._sessions.get(sid) else None
                    sessions.append({
                        "key": sid,
                        "lastMessage": last_msg.content[:100] if last_msg else None,
                        "messageCount": meta["message_count"],
                        "createdAt": meta["created_at"],
                        "activeMinutes": int((now - created).total_seconds() / 60),
                    })
                    if len(sessions) >= limit:
                        break
        
        return {"sessions": sessions, "total": len(sessions)}
    
    async def _handle_sessions_patch(self, data: dict) -> dict:
        session_key = data.get("sessionKey")
        if not session_key:
            return {"success": False, "error": "sessionKey required"}
        
        async with self._lock:
            if session_key not in self._sessions_meta:
                self._sessions_meta[session_key] = {"created_at": datetime.now().isoformat(), "message_count": 0}
            
            for key, value in data.items():
                if key != "sessionKey":
                    self._sessions_meta[session_key][key] = value
        
        return {"success": True}
    
    async def _handle_sessions_delete(self, data: dict) -> dict:
        session_key = data.get("key")
        if not session_key:
            return {"success": False, "error": "key required"}
        
        async with self._lock:
            if session_key in self._sessions:
                del self._sessions[session_key]
            if session_key in self._sessions_meta:
                del self._sessions_meta[session_key]
        
        return {"success": True}
    
    async def _handle_agents_list(self, data: dict) -> dict:
        return {
            "agents": [{"id": "default", "name": "Default Agent"}],
            "defaultId": "default",
        }
    
    async def _handle_channels_status(self, data: dict) -> dict:
        from kaolalabot.config.loader import load_config

        config = load_config()
        return {
            "sources": [
                {"name": "web", "displayName": "Web", "configured": True},
                {
                    "name": "feishu",
                    "displayName": "Feishu",
                    "configured": bool(config.channels.feishu.enabled),
                },
                {
                    "name": "dingtalk",
                    "displayName": "DingTalk",
                    "configured": bool(
                        getattr(config.channels, "dingtalk", None)
                        and config.channels.dingtalk.enabled
                    ),
                },
                {
                    "name": "mcp",
                    "displayName": "MCP",
                    "configured": bool(getattr(config, "mcp", None) and config.mcp.enabled),
                },
            ]
        }

    async def handle_request(self, method: str, data: dict) -> dict:
        """Handle incoming RPC request."""
        handler = self._handlers.get(method)
        
        if not handler:
            return {
                "error": f"Unknown method: {method}",
                "code": "METHOD_NOT_FOUND",
            }
        
        try:
            return await handler(data)
        except Exception as e:
            logger.exception(f"Error handling {method}: {e}")
            return {
                "error": str(e),
                "code": "INTERNAL_ERROR",
            }
    
    def register_handler(self, method: str, handler: RPCMethod) -> None:
        """Register custom RPC handler."""
        self._handlers[method] = handler
    
    async def get_session_messages(self, session_key: str) -> list[ChatMessage]:
        """Get all messages for a session."""
        async with self._lock:
            return list(self._sessions.get(session_key, []))
    
    async def clear_session(self, session_key: str) -> bool:
        """Clear a session."""
        async with self._lock:
            if session_key in self._sessions:
                del self._sessions[session_key]
            if session_key in self._sessions_meta:
                del self._sessions_meta[session_key]
                return True
            return False


_rpc_protocol: Optional[GatewayRPCProtocol] = None


def get_rpc_protocol() -> GatewayRPCProtocol:
    """Get the global RPC protocol handler."""
    global _rpc_protocol
    if _rpc_protocol is None:
        _rpc_protocol = GatewayRPCProtocol()
    return _rpc_protocol
