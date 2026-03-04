"""Voice integration example - 如何将语音模式集成到聊天系统

这个文件展示了如何将语音服务集成到现有的聊天系统中。
你可以根据需要修改或参考这个模式。
"""

import asyncio
from typing import Optional

from loguru import logger

from kaolalabot.voice import VoiceService, VoiceConfig
from kaolalabot.agent.loop import AgentLoop


class ChatSystemWithVoice:
    """
    集成语音功能的聊天系统示例
    
    功能:
    - 文本聊天模式
    - 语音聊天模式
    - 模式切换
    - 对话上下文保持
    """
    
    def __init__(self, agent_loop: AgentLoop):
        self.agent_loop = agent_loop
        self.voice_service: Optional[VoiceService] = None
        self.voice_enabled = False
        self.current_session_key = "chat:default"
    
    async def initialize_voice(
        self,
        config: Optional[VoiceConfig] = None,
    ) -> None:
        """
        初始化语音服务
        
        Args:
            config: 语音配置
        """
        self.voice_service = VoiceService(
            config=config,
            agent_loop=self.agent_loop,
        )
        
        # 设置回调
        self.voice_service.set_on_text_recognized(self._on_voice_text)
        self.voice_service.set_on_agent_response(self._on_voice_response)
        self.voice_service.set_on_state_change(self._on_voice_state)
        
        logger.info("语音服务已初始化")
    
    async def enable_voice(self) -> bool:
        """
        启用语音模式
        
        Returns:
            是否成功启用
        """
        if not self.voice_service:
            await self.initialize_voice()
        
        if self.voice_enabled:
            logger.info("语音模式已经启用")
            return True
        
        success = await self.voice_service.start()
        if success:
            self.voice_enabled = True
            logger.info("已切换到语音模式")
        else:
            logger.error("语音模式启动失败")
        
        return success
    
    async def disable_voice(self) -> None:
        """禁用语音模式"""
        if not self.voice_enabled:
            return
        
        await self.voice_service.stop()
        self.voice_enabled = False
        logger.info("已切换到文本模式")
    
    async def toggle_voice(self) -> bool:
        """
        切换语音模式
        
        Returns:
            切换后的状态
        """
        if self.voice_enabled:
            await self.disable_voice()
        else:
            await self.enable_voice()
        
        return self.voice_enabled
    
    async def process_text_message(self, text: str) -> str:
        """
        处理文本消息
        
        Args:
            text: 用户输入
            
        Returns:
            Agent回复
        """
        response = await self.agent_loop.process_direct(
            content=text,
            session_key=self.current_session_key,
            channel="chat",
        )
        return response
    
    async def process_voice_input(self, audio_data: bytes) -> str:
        """
        处理语音输入
        
        Args:
            audio_data: 音频数据
            
        Returns:
            识别到的文本
        """
        # TODO: 实现音频到文本的转换
        # 可以调用 ASR 模块
        return ""
    
    async def speak_response(self, text: str) -> None:
        """
        朗读回复文本
        
        Args:
            text: 要朗读的文本
        """
        # TODO: 实现 TTS 播放
        pass
    
    async def _on_voice_text(self, text: str) -> None:
        """
        语音识别完成回调
        """
        logger.info(f"识别到文本: {text}")
        
        # 处理识别到的文本
        response = await self.process_text_message(text)
        
        # 朗读回复
        await self.speak_response(response)
    
    async def _on_voice_response(self, response: str) -> None:
        """
        Agent回复回调
        """
        logger.info(f"Agent回复: {response}")
    
    async def _on_voice_state(self, state: str) -> None:
        """
        状态变化回调
        """
        logger.info(f"语音状态: {state}")
    
    def get_status(self) -> dict:
        """获取状态"""
        return {
            "voice_enabled": self.voice_enabled,
            "voice_service_running": (
                self.voice_service.is_running 
                if self.voice_service else False
            ),
            "session_key": self.current_session_key,
        }


# ====== 使用示例 ======

async def example_usage():
    """使用示例"""
    from kaolalabot.config import load_config
    from kaolalabot.bus.queue import MessageBus
    from kaolalabot.providers.litellm_provider import LiteLLMProvider
    from pathlib import Path
    
    # 初始化组件
    config = load_config()
    bus = MessageBus()
    provider = LiteLLMProvider(
        api_key=config.get_api_key(),
        api_base=config.get_api_base(),
    )
    workspace = Path("workspace")
    
    # 创建AgentLoop
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
    )
    
    # 创建带语音的聊天系统
    chat = ChatSystemWithVoice(agent_loop)
    
    # 初始化语音服务（但不启用）
    await chat.initialize_voice()
    
    # 文本模式对话
    response = await chat.process_text_message("你好")
    print(f"文本回复: {response}")
    
    # 启用语音模式
    await chat.enable_voice()
    
    # 获取状态
    print(chat.get_status())
    
    # 禁用语音模式
    await chat.disable_voice()


# ====== CLI命令集成示例 ======

async def voice_command_handler(args):
    """处理 voice 命令"""
    from kaolalabot.voice import VoiceConfig
    
    config = VoiceConfig(
        sample_rate=args.sample_rate,
        vad_aggressiveness=args.vad_level,
        asr_model_size=args.asr_model,
        tts_voice=args.tts_voice,
    )
    
    # 根据参数决定动作
    if args.start:
        # 启动语音服务
        service = VoiceService(config=config)
        await service.start()
        print("语音服务已启动")
        
    elif args.stop:
        # 停止语音服务
        service = VoiceService(config=config)
        await service.stop()
        print("语音服务已停止")
        
    elif args.status:
        # 查看状态
        service = VoiceService(config=config)
        print(service.get_status())


if __name__ == "__main__":
    asyncio.run(example_usage())
