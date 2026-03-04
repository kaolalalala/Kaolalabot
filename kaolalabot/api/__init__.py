"""API routes for kaolalabot - Gateway integration with OpenClaw-style protocol."""

import uuid
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from kaolalabot import server_config
from kaolalabot.memory.manager import MemoryManager
from kaolalabot.config.loader import load_config
from kaolalabot.providers.litellm_provider import LiteLLMProvider
from kaolalabot.gateway import get_rpc_protocol, get_gateway_auth
from kaolalabot.gateway.remote import get_remote_manager
from kaolalabot.channels.manager import ChannelManager

api_router = APIRouter()

memory_manager: Optional[MemoryManager] = None
llm_provider: Optional[LiteLLMProvider] = None


def get_memory_manager() -> MemoryManager:
    """Get or create memory manager."""
    global memory_manager
    if memory_manager is None:
        memory_manager = MemoryManager(
            workspace=server_config.settings.workspace_path_expanded,
            working_capacity=server_config.settings.memory_working_capacity,
            episodic_retention_days=server_config.settings.memory_episodic_retention_days,
        )
    return memory_manager


def get_llm_provider() -> LiteLLMProvider:
    """Get or create LLM provider."""
    global llm_provider
    if llm_provider is None:
        # 获取provider名称和模型
        config = load_config()
        provider_name = config.agents.defaults.provider
        model = config.agents.defaults.model
        
        # 获取对应的API key
        api_key = config.get_api_key(model)
        api_base = config.get_api_base(model)
        
        llm_provider = LiteLLMProvider(
            api_key=api_key,
            api_base=api_base,
            default_model=model,
            provider_name=provider_name if provider_name != "auto" else None,
        )
    return llm_provider


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    content: str
    session_id: str
    thinking_id: str = ""
    thinking_steps: list[dict] = []


@api_router.post("/chat/send", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Send a message to the agent."""
    try:
        session_id = request.session_id or str(uuid.uuid4())
        
        memory = get_memory_manager()
        provider = get_llm_provider()
        
        # 检索相关记忆作为上下文
        context = await memory.recall(request.message, session_id)
        
        # 构建上下文消息
        context_msgs = []
        for m in context[-5:]:  # 最近5条
            context_msgs.append({"role": "user", "content": m.content})
        
        # 保存用户消息到工作记忆
        await memory.add(
            content=f"User: {request.message}",
            memory_level="working",
            session_id=session_id,
        )
        
        # 调用LLM
        thinking_steps = []
        
        # 观察阶段
        thinking_steps.append({
            "phase": "observe",
            "content": f"理解用户需求: {request.message[:50]}...",
            "confidence": 0.9
        })
        
        # 推理阶段
        thinking_steps.append({
            "phase": "reason",
            "content": "分析问题并规划回答策略",
            "confidence": 0.85
        })
        
        # 调用LLM生成回答
        response = await provider.chat([
            {"role": "system", "content": "你是一个有用的AI助手。"},
            *context_msgs,
            {"role": "user", "content": request.message}
        ])
        
        final_content = response.content if response.content else "抱歉，我无法生成回答。"
        
        # 行动阶段
        thinking_steps.append({
            "phase": "act",
            "content": final_content[:100],
            "confidence": 0.8
        })
        
        # 保存回复到情景记忆
        await memory.add(
            content=f"Assistant: {final_content}",
            memory_level="episodic",
            session_id=session_id,
        )
        
        # 反思阶段
        thinking_steps.append({
            "phase": "reflect",
            "content": "回答已生成并保存到记忆",
            "confidence": 0.75
        })
        
        thinking_id = f"think-{session_id[:8]}"
        
        return ChatResponse(
            content=final_content,
            session_id=session_id,
            thinking_id=thinking_id,
            thinking_steps=thinking_steps,
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/memory/short")
async def get_short_term_memory(session_id: Optional[str] = None):
    """Get short-term (working) memory."""
    memory = get_memory_manager()
    memories = await memory.get_working()
    return {"memories": [_memory_to_dict(m) for m in memories]}


@api_router.get("/memory/mid")
async def get_mid_term_memory(limit: int = 20, offset: int = 0):
    """Get mid-term (episodic) memory."""
    memory = get_memory_manager()
    memories = await memory.get_episodic(limit=limit, offset=offset)
    return {"memories": [_memory_to_dict(m) for m in memories]}


@api_router.get("/memory/long")
async def get_long_term_memory(query: Optional[str] = None, limit: int = 10):
    """Get long-term (semantic) memory."""
    memory = get_memory_manager()
    if query:
        memories = await memory.get_semantic(query, limit=limit)
    else:
        memories = await memory.get_episodic(limit=limit)
    return {"memories": [_memory_to_dict(m) for m in memories]}


@api_router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a memory."""
    memory = get_memory_manager()
    success = await memory.delete(memory_id)
    return {"success": success}


@api_router.post("/memory/{memory_id}/promote")
async def promote_memory(memory_id: str):
    """Promote a memory to long-term storage."""
    memory = get_memory_manager()
    result = await memory.promote(memory_id)
    return {"success": result is not None, "memory": _memory_to_dict(result) if result else None}


@api_router.get("/status")
async def get_status():
    """Get system status."""
    from kaolalabot.config.loader import load_config
    config = load_config()
    
    rpc = get_rpc_protocol()
    auth = get_gateway_auth()
    remote = get_remote_manager()
    
    memory = get_memory_manager()
    return {
        "status": "running",
        "version": "1.0.0",
        "workspace": str(server_config.settings.workspace_path_expanded),
        "agent_model": config.agents.defaults.model,
        "provider": config.agents.defaults.provider,
        "gateway": {
            "auth": auth.get_config(),
            "remote": remote.get_config(),
        },
        "memory_stats": {
            "working": len(await memory.get_working()),
        },
    }


class RPCRequest(BaseModel):
    method: str
    data: dict = {}


@api_router.post("/gateway/rpc")
async def gateway_rpc(request: RPCRequest):
    """Gateway RPC endpoint - OpenClaw style."""
    rpc = get_rpc_protocol()
    result = await rpc.handle_request(request.method, request.data)
    return result


@api_router.post("/gateway/rpc/{method}")
async def gateway_rpc_method(method: str, data: dict = {}):
    """Gateway RPC endpoint by method name."""
    rpc = get_rpc_protocol()
    result = await rpc.handle_request(method, data)
    return result


@api_router.get("/gateway/sessions")
async def list_sessions():
    """List all sessions."""
    rpc = get_rpc_protocol()
    return await rpc.handle_request("sessions.list", {})


@api_router.delete("/gateway/sessions/{session_key}")
async def delete_session(session_key: str):
    """Delete a session."""
    rpc = get_rpc_protocol()
    return await rpc.handle_request("sessions.delete", {"key": session_key})


@api_router.get("/gateway/channels")
async def channels_status():
    """Get channels status."""
    rpc = get_rpc_protocol()
    return await rpc.handle_request("channels.status", {})


@api_router.post("/channels/dingtalk/callback")
async def dingtalk_callback(request: Request):
    """DingTalk inbound callback entry."""
    manager = ChannelManager.get_active()
    if manager is None:
        raise HTTPException(status_code=503, detail="Channel manager not ready")

    channel = manager.get_dingtalk_channel()
    if channel is None:
        raise HTTPException(status_code=404, detail="DingTalk channel not enabled")

    payload = await request.json()
    return await channel.handle_callback(payload)


@api_router.get("/channels/dingtalk/status")
async def dingtalk_status():
    """Return DingTalk channel runtime status."""
    manager = ChannelManager.get_active()
    if manager is None:
        raise HTTPException(status_code=503, detail="Channel manager not ready")

    channel = manager.get_dingtalk_channel()
    if channel is None:
        return {"enabled": False, "running": False}

    status = channel.status()
    status["enabled"] = True
    return status


@api_router.get("/gateway/agents")
async def agents_list():
    """List available agents."""
    rpc = get_rpc_protocol()
    return await rpc.handle_request("agents.list", {})


from kaolalabot.gateway.remote import get_remote_manager


def _memory_to_dict(memory) -> dict:
    """Convert memory object to dict."""
    if hasattr(memory, '__dict__'):
        d = memory.__dict__.copy()
        for key, value in d.items():
            if hasattr(value, 'isoformat'):
                d[key] = value.isoformat()
        return d
    return {}
