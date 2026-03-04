"""Voice channel for Gateway

语音通道 - 作为Gateway的一个通道运行
"""

import asyncio
from typing import Any

from loguru import logger

from kaolalabot.bus.events import OutboundMessage
from kaolalabot.bus.queue import MessageBus
from kaolalabot.channels.base import BaseChannel
from kaolalabot.config.schema import FeishuConfig


class VoiceChannel(BaseChannel):
    """
    语音通道 - 通过麦克风接收语音输入
    
    功能:
    - 监听麦克风
    - VAD语音检测
    - ASR语音识别
    - Agent处理
    - TTS语音合成输出
    """
    
    name = "voice"
    
    def __init__(self, config: dict | None = None, bus: MessageBus | None = None, agent_loop=None):
        from dataclasses import dataclass, field
        
        @dataclass
        class VoiceChannelConfig:
            enabled: bool = True
            sample_rate: int = 16000
            vad_aggressiveness: int = 1
            vad_min_silence_duration_ms: int = 5000
            vad_energy_threshold: float = 500.0
            asr_model_size: str = "tiny"
            asr_device: str = "auto"
            tts_voice: str = "zh-CN-XiaoxiaoNeural"
            
        voice_config = config or {}
        parsed_config = VoiceChannelConfig(
            enabled=voice_config.get("enabled", True),
            sample_rate=voice_config.get("sample_rate", 16000),
            vad_aggressiveness=voice_config.get("vad_aggressiveness", 1),
            vad_min_silence_duration_ms=voice_config.get("vad_min_silence_duration_ms", 5000),
            vad_energy_threshold=voice_config.get("vad_energy_threshold", 500.0),
            asr_model_size=voice_config.get("asr_model_size", "tiny"),
            asr_device=voice_config.get("asr_device", "auto"),
            tts_voice=voice_config.get("tts_voice", "zh-CN-XiaoxiaoNeural"),
        )
        
        super().__init__(parsed_config, bus)
        self._voice_shell = None
        self._agent_loop = agent_loop
    
    async def start(self) -> None:
        """启动语音通道"""
        from kaolalabot.voice import VoiceShell, VoiceConfig
        
        logger.info("Starting Voice channel...")
        
        # 创建语音配置
        config = VoiceConfig(
            sample_rate=self.config.sample_rate,
            vad_aggressiveness=self.config.vad_aggressiveness,
            vad_min_silence_duration_ms=self.config.vad_min_silence_duration_ms,
            vad_energy_threshold=self.config.vad_energy_threshold,
            asr_model_size=self.config.asr_model_size,
            asr_device=self.config.asr_device,
            tts_voice=self.config.tts_voice,
        )
        
        # 创建VoiceShell并连接Agent
        self._voice_shell = VoiceShell(
            config=config,
            agent_loop=self._agent_loop,
        )
        
        # 初始化并启动
        await self._voice_shell.initialize()
        await self._voice_shell.start()
        
        self._running = True
        logger.info("Voice channel started - 请对着麦克风说话")
    
    async def stop(self) -> None:
        """停止语音通道"""
        if self._voice_shell:
            await self._voice_shell.stop()
        
        self._running = False
        logger.info("Voice channel stopped")
    
    async def send(self, msg: OutboundMessage) -> None:
        """发送消息（暂不需要）"""
        # 语音通道主要是输入，输出通过TTS直接播放
        pass
    
    def is_allowed(self, sender_id: str) -> bool:
        """检查是否允许（语音通道无限制）"""
        return True
