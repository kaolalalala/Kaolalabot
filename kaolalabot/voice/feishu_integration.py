"""Feishu Voice Integration - 飞书语音模式集成

将语音命令处理集成到飞书通道中
"""

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from kaolalabot.voice.service import VoiceService


class FeishuVoiceMixin:
    """
    飞书语音模式Mixin
    
    在FeishuChannel类中混入此模块以支持语音命令
    """
    
    _voice_service: "VoiceService | None" = None
    
    # 语音命令模式
    VOICE_COMMAND_PATTERNS = [
        "开启语音",
        "启动语音", 
        "打开语音",
        "语音模式",
        "关闭语音",
        "停止语音",
        "语音状态",
        "语音帮助",
        "/语音",
        "/voice on",
        "/voice off",
    ]
    
    def set_voice_service(self, service: "VoiceService") -> None:
        """设置语音服务"""
        self._voice_service = service
        logger.info("Feishu voice service set")
    
    @property
    def voice_service(self) -> "VoiceService | None":
        """获取语音服务"""
        return self._voice_service
    
    def is_voice_command(self, content: str) -> bool:
        """检查是否是语音命令"""
        if not content:
            return False
        
        content = content.strip()
        
        # 检查是否匹配任何语音命令模式
        for pattern in self.VOICE_COMMAND_PATTERNS:
            if content == pattern or content.lower().startswith(pattern.lower()):
                return True
        
        return False
    
    async def handle_voice_command(self, content: str) -> str | None:
        """
        处理语音命令
        
        Args:
            content: 消息内容
            
        Returns:
            命令响应或None(不是命令时)
        """
        if not self.is_voice_command(content):
            return None
        
        if not self._voice_service:
            return "❌ 语音服务未初始化"
        
        try:
            content_lower = content.strip().lower()
            
            # 开启语音
            if content_lower in ("开启语音", "启动语音", "打开语音", "语音模式", "/语音"):
                if self._voice_service.is_running:
                    return "🔊 语音模式已经是开启状态"
                success = await self._voice_service.start()
                if success:
                    return "🔊 语音模式已开启！请对着麦克风说话。"
                return "❌ 语音模式启动失败"
            
            # 关闭语音
            elif content_lower in ("关闭语音", "停止语音", "/voice off"):
                if not self._voice_service.is_running:
                    return "🔇 语音模式已经是关闭状态"
                await self._voice_service.stop()
                return "🔇 语音模式已关闭"
            
            # 语音状态
            elif content_lower in ("语音状态", "/voice status"):
                if not self._voice_service:
                    return "❌ 语音服务未初始化"
                status = self._voice_service.get_status()
                running = status.get("running", False)
                state = status.get("state", "unknown")
                if running:
                    return f"🔊 语音模式: 开启\n状态: {state}"
                return "🔇 语音模式: 关闭"
            
            # 语音帮助
            elif content_lower in ("语音帮助", "/voice help"):
                return """📖 语音模式命令:
• 开启语音 / 启动语音 / 语音模式 → 开启语音输入
• 关闭语音 / 停止语音 → 关闭语音输入  
• 语音状态 → 查看当前状态
• 语音帮助 → 显示此帮助"""
            
            return None
            
        except Exception as e:
            logger.error(f"Voice command error: {e}")
            return f"❌ 命令执行失败: {e}"


def integrate_voice_to_feishu(feishu_channel, voice_service: "VoiceService") -> None:
    """
    将语音服务集成到飞书通道
    
    Args:
        feishu_channel: FeishuChannel实例
        voice_service: VoiceService实例
    """
    # 使用mixin方式添加方法
    for name in dir(FeishuVoiceMixin):
        if not name.startswith("_"):
            attr = getattr(FeishuVoiceMixin, name)
            if callable(attr):
                setattr(feishu_channel, name, getattr(feishu_channel, name, None) or attr)
    
    feishu_channel.set_voice_service(voice_service)
    logger.info("Voice integrated to Feishu channel")
