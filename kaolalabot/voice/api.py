"""Voice API - 语音模式Web API接口

为语音模式预留的Web接口，方便未来开发独立的语音网页界面
"""

from __future__ import annotations

import asyncio
import base64
import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger

if TYPE_CHECKING:
    from kaolalabot.voice.service import VoiceService

router = APIRouter(prefix="/voice", tags=["voice"])

_voice_service: "VoiceService | None" = None


def set_voice_service(service: "VoiceService") -> None:
    """设置语音服务实例"""
    global _voice_service
    _voice_service = service


def get_voice_service() -> "VoiceService | None":
    """获取语音服务实例"""
    return _voice_service


class VoiceWebSocketManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Voice WebSocket connected: {client_id}")
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Voice WebSocket disconnected: {client_id}")
    
    async def send_text(self, client_id: str, text: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json({
                "type": "text",
                "content": text,
            })
    
    async def send_audio(self, client_id: str, audio_data: bytes):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json({
                "type": "audio",
                "content": base64.b64encode(audio_data).decode("utf-8"),
            })
    
    async def send_state(self, client_id: str, state: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json({
                "type": "state",
                "state": state,
            })
    
    async def broadcast_state(self, state: str):
        for client_id in list(self.active_connections.keys()):
            await self.send_state(client_id, state)


ws_manager = VoiceWebSocketManager()


@router.get("/status")
async def get_voice_status():
    """获取语音服务状态"""
    service = get_voice_service()
    if not service:
        return {
            "enabled": False,
            "message": "Voice service not initialized",
        }
    
    return service.get_status()


@router.post("/start")
async def start_voice():
    """启动语音服务"""
    service = get_voice_service()
    if not service:
        raise HTTPException(status_code=500, detail="Voice service not initialized")
    
    if service.is_running:
        return {"status": "already_running"}
    
    success = await service.start()
    if success:
        await ws_manager.broadcast_state("started")
        return {"status": "started"}
    
    raise HTTPException(status_code=500, detail="Failed to start voice service")


@router.post("/stop")
async def stop_voice():
    """停止语音服务"""
    service = get_voice_service()
    if not service:
        raise HTTPException(status_code=500, detail="Voice service not initialized")
    
    if not service.is_running:
        return {"status": "already_stopped"}
    
    await service.stop()
    await ws_manager.broadcast_state("stopped")
    return {"status": "stopped"}


@router.post("/config")
async def update_voice_config(config: dict):
    """更新语音配置"""
    service = get_voice_service()
    if not service:
        raise HTTPException(status_code=500, detail="Voice service not initialized")
    
    # 更新配置
    if "vad_aggressiveness" in config:
        service.config.vad_aggressiveness = config["vad_aggressiveness"]
    if "asr_model_size" in config:
        service.config.asr_model_size = config["asr_model_size"]
    if "tts_voice" in config:
        service.config.tts_voice = config["tts_voice"]
    
    return {"status": "updated", "config": service.config.__dict__}


@router.websocket("/ws/{client_id}")
async def voice_websocket(websocket: WebSocket, client_id: str):
    """
    语音WebSocket接口
    
    支持:
    - 客户端发送音频数据
    - 服务端发送识别结果/合成音频/状态更新
    """
    await ws_manager.connect(client_id, websocket)
    
    try:
        # 发送欢迎消息
        await websocket.send_json({
            "type": "welcome",
            "client_id": client_id,
            "message": "Connected to voice service",
        })
        
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            msg_type = message.get("type")
            
            if msg_type == "audio":
                # 处理客户端发送的音频数据
                audio_base64 = message.get("content", "")
                audio_data = base64.b64decode(audio_base64)
                
                # TODO: 发送给VAD/ASR处理
                # 这里预留接口，未来可以实现流式语音识别
                
            elif msg_type == "text":
                # 处理文本消息
                text = message.get("content", "")
                await ws_manager.send_text(client_id, f"Echo: {text}")
                
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"Voice WebSocket error: {e}")
        ws_manager.disconnect(client_id)


@router.post("/tts/speak")
async def text_to_speak(text: str):
    """
    文字转语音接口
    
    用于将文字转换为语音并返回
    """
    service = get_voice_service()
    if not service:
        raise HTTPException(status_code=500, detail="Voice service not initialized")
    
    # TODO: 实现TTS调用
    return {
        "status": "not_implemented",
        "message": "TTS endpoint not implemented yet",
    }


@router.post("/asr/recognize")
async def audio_to_text(audio_base64: str):
    """
    语音识别接口
    
    用于将音频数据识别为文字
    """
    service = get_voice_service()
    if not service:
        raise HTTPException(status_code=500, detail="Voice service not initialized")
    
    # TODO: 实现ASR调用
    return {
        "status": "not_implemented", 
        "message": "ASR endpoint not implemented yet",
    }


def create_voice_router(service: "VoiceService") -> APIRouter:
    """
    创建语音路由器的工厂函数
    
    Args:
        service: VoiceService实例
        
    Returns:
        配置好的APIRouter
    """
    set_voice_service(service)
    return router
