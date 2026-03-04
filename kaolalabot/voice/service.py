"""Voice Service - 独立的语音服务层

将VoiceShell封装为独立服务，与主聊天系统解耦
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable, Awaitable

from loguru import logger

if TYPE_CHECKING:
    from kaolalabot.voice.shell import VoiceShell
    from kaolalabot.voice.config import VoiceConfig


class VoiceService:
    """
    语音服务 - 管理语音交互的生命周期
    
    特点:
    - 独立于主聊天系统
    - 可随时启停
    - 支持回调函数处理识别结果
    - 保留完整状态管理
    """

    def __init__(
        self,
        config: "VoiceConfig | None" = None,
        agent_loop=None,
    ):
        """
        初始化语音服务
        
        Args:
            config: 语音配置
            agent_loop: AgentLoop实例（可选，用于处理识别后的文本）
        """
        from kaolalabot.voice import VoiceConfig
        
        self._config = config or VoiceConfig()
        self._agent_loop = agent_loop
        self._shell: VoiceShell | None = None
        self._running = False
        
        self._on_text_recognized: Callable[[str], Awaitable[None]] | None = None
        self._on_agent_response: Callable[[str], Awaitable[None]] | None = None
        self._on_state_change: Callable[[str], Awaitable[None]] | None = None

    @property
    def is_running(self) -> bool:
        """检查服务是否运行中"""
        return self._running

    @property
    def config(self) -> "VoiceConfig":
        """获取配置"""
        return self._config

    def set_on_text_recognized(
        self, 
        callback: Callable[[str], Awaitable[None]] | None
    ) -> None:
        """设置文本识别回调"""
        self._on_text_recognized = callback

    def set_on_agent_response(
        self, 
        callback: Callable[[str], Awaitable[None]] | None
    ) -> None:
        """设置Agent回复回调"""
        self._on_agent_response = callback

    def set_on_state_change(
        self, 
        callback: Callable[[str], Awaitable[None]] | None
    ) -> None:
        """设置状态变化回调"""
        self._on_state_change = callback

    async def start(self) -> bool:
        """
        启动语音服务
        
        Returns:
            是否启动成功
        """
        if self._running:
            logger.warning("VoiceService already running")
            return True

        try:
            from kaolalabot.voice import VoiceShell
            
            logger.info("Starting VoiceService...")
            
            self._shell = VoiceShell(
                config=self._config,
                agent_loop=self._agent_loop,
            )
            
            await self._shell.initialize()
            await self._shell.start()
            
            self._running = True
            logger.info("VoiceService started successfully")
            
            if self._on_state_change:
                await self._on_state_change("started")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start VoiceService: {e}")
            return False

    async def stop(self) -> None:
        """停止语音服务"""
        if not self._running:
            return

        logger.info("Stopping VoiceService...")
        
        if self._shell:
            await self._shell.stop()
            self._shell = None
        
        self._running = False
        logger.info("VoiceService stopped")
        
        if self._on_state_change:
            await self._on_state_change("stopped")

    async def restart(self) -> bool:
        """重启语音服务"""
        await self.stop()
        await asyncio.sleep(0.5)
        return await self.start()

    def get_status(self) -> dict:
        """获取服务状态"""
        if not self._shell:
            return {
                "running": False,
                "state": "not_initialized",
            }
        
        return self._shell.get_status()

    async def process_text(self, text: str) -> str | None:
        """
        处理文本（当使用语音识别后）
        
        Args:
            text: 识别到的文本
            
        Returns:
            Agent回复文本
        """
        if not self._agent_loop:
            return None
        
        try:
            response = await self._agent_loop.process_direct(
                content=text,
                session_key="voice:session",
                channel="voice",
            )
            return response
        except Exception as e:
            logger.error(f"Error processing text: {e}")
            return None


class VoiceServiceManager:
    """
    语音服务管理器 - 方便在多处使用语音服务
    
    这是单例模式，方便全局访问
    """
    
    _instance: VoiceService | None = None
    _lock = asyncio.Lock()
    
    @classmethod
    async def get_instance(
        cls,
        config: "VoiceConfig | None" = None,
        agent_loop=None,
    ) -> VoiceService:
        """获取语音服务单例"""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = VoiceService(
                    config=config,
                    agent_loop=agent_loop,
                )
            return cls._instance
    
    @classmethod
    async def start_service(
        cls,
        config: "VoiceConfig | None" = None,
        agent_loop=None,
    ) -> VoiceService:
        """启动语音服务"""
        service = await cls.get_instance(config, agent_loop)
        await service.start()
        return service
    
    @classmethod
    async def stop_service(cls) -> None:
        """停止语音服务"""
        if cls._instance:
            await cls._instance.stop()
    
    @classmethod
    def get_service(cls) -> VoiceService | None:
        """获取当前服务实例"""
        return cls._instance


async def create_voice_service(
    config_path: str | None = None,
    agent_loop=None,
) -> VoiceService:
    """
    创建语音服务的工厂函数
    
    Args:
        config_path: 配置文件路径
        agent_loop: AgentLoop实例
        
    Returns:
        VoiceService实例
    """
    from pathlib import Path
    
    config = None
    if config_path and Path(config_path).exists():
        import yaml
        with open(config_path) as f:
            data = yaml.safe_load(f)
            if data and "voice" in data:
                from kaolalabot.voice import VoiceConfig
                voice_cfg = data["voice"]
                config = VoiceConfig(
                    sample_rate=voice_cfg.get("sample_rate", 16000),
                    vad_aggressiveness=voice_cfg.get("vad_aggressiveness", 3),
                    asr_model_size=voice_cfg.get("asr_model_size", "tiny"),
                    tts_voice=voice_cfg.get("tts_voice", "zh-CN-XiaoxiaoNeural"),
                )
    
    service = VoiceService(config=config, agent_loop=agent_loop)
    return service
