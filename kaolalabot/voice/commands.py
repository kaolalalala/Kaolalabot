"""Voice commands handler for chat channels

支持在聊天中通过文字指令开启/关闭语音模式
"""

import re
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from kaolalabot.voice.service import VoiceService

VOICE_COMMANDS = {
    # 开启语音
    "开启语音": "start",
    "启动语音": "start",
    "打开语音": "start",
    "语音模式": "start",
    "voice on": "start",
    "voice start": "start",
    "/voice on": "start",
    "/语音": "start",
    
    # 关闭语音
    "关闭语音": "stop",
    "停止语音": "stop",
    "关闭语音模式": "stop",
    "voice off": "stop",
    "voice stop": "stop",
    "/voice off": "stop",
    
    # 查询状态
    "语音状态": "status",
    "语音模式状态": "status",
    "voice status": "status",
    "/voice status": "status",
    
    # 帮助
    "语音帮助": "help",
    "voice help": "help",
    "/voice help": "help",
}


class VoiceCommandHandler:
    """
    语音命令处理器
    
    在聊天消息中检测语音相关命令并执行
    """
    
    def __init__(self, voice_service: "VoiceService | None" = None):
        self._voice_service = voice_service
        self._enabled = True
    
    def set_voice_service(self, service: "VoiceService") -> None:
        """设置语音服务"""
        self._voice_service = service
    
    @property
    def voice_service(self) -> "VoiceService | None":
        return self._voice_service
    
    def is_enabled(self) -> bool:
        """检查是否启用"""
        return self._enabled
    
    def enable(self) -> None:
        """启用命令处理"""
        self._enabled = True
    
    def disable(self) -> None:
        """禁用命令处理"""
        self._enabled = False
    
    async def process_message(self, content: str) -> str | None:
        """
        处理消息，检查是否是语音命令
        
        Args:
            content: 消息内容
            
        Returns:
            如果是命令返回响应消息，否则返回None
        """
        if not self._enabled:
            return None
        
        # 去除首尾空白
        content = content.strip()
        
        # 检查是否是语音命令
        command = self._match_command(content)
        if not command:
            return None
        
        logger.info(f"Voice command detected: {command}")
        
        # 执行命令
        return await self._execute_command(command)
    
    def _match_command(self, content: str) -> str | None:
        """匹配命令"""
        # 完全匹配
        if content in VOICE_COMMANDS:
            return VOICE_COMMANDS[content]
        
        # 忽略大小写匹配
        content_lower = content.lower()
        for cmd, action in VOICE_COMMANDS.items():
            if cmd.lower() == content_lower:
                return action
        
        # 前缀匹配
        for cmd, action in VOICE_COMMANDS.items():
            if content.startswith(cmd):
                return action
        
        return None
    
    async def _execute_command(self, command: str) -> str:
        """执行命令"""
        if not self._voice_service:
            return "❌ 语音服务未初始化，请先启动语音服务"
        
        try:
            if command == "start":
                if self._voice_service.is_running:
                    return "🔊 语音模式已经是开启状态"
                
                success = await self._voice_service.start()
                if success:
                    return "🔊 语音模式已开启！请对着麦克风说话。"
                else:
                    return "❌ 语音模式启动失败，请检查日志"
            
            elif command == "stop":
                if not self._voice_service.is_running:
                    return "🔇 语音模式已经是关闭状态"
                
                await self._voice_service.stop()
                return "🔇 语音模式已关闭"
            
            elif command == "status":
                if not self._voice_service:
                    return "❌ 语音服务未初始化"
                
                status = self._voice_service.get_status()
                running = status.get("running", False)
                state = status.get("state", "unknown")
                
                if running:
                    return f"🔊 语音模式状态: 开启\n状态: {state}"
                else:
                    return "🔇 语音模式状态: 关闭"
            
            elif command == "help":
                return self._get_help_text()
            
            else:
                return f"❓ 未知命令: {command}"
        
        except Exception as e:
            logger.error(f"Voice command error: {e}")
            return f"❌ 命令执行失败: {e}"
    
    def _get_help_text(self) -> str:
        """获取帮助文本"""
        return """📖 语音模式命令帮助

开启语音:
  - 开启语音
  - 启动语音
  - 语音模式
  - /语音

关闭语音:
  - 关闭语音
  - 停止语音

查看状态:
  - 语音状态

帮助:
  - 语音帮助

💡 开启语音后，请对着麦克风说话，系统会自动识别并回复。
"""


# 全局命令处理器实例
_command_handler: VoiceCommandHandler | None = None


def get_voice_command_handler() -> VoiceCommandHandler:
    """获取语音命令处理器单例"""
    global _command_handler
    if _command_handler is None:
        _command_handler = VoiceCommandHandler()
    return _command_handler


async def handle_voice_command(content: str) -> str | None:
    """
    处理语音命令的便捷函数
    
    Args:
        content: 消息内容
        
    Returns:
        命令响应或None
    """
    handler = get_voice_command_handler()
    return await handler.process_message(content)


def set_voice_service_for_commands(service: "VoiceService") -> None:
    """
    为命令处理器设置语音服务
    
    Args:
        service: VoiceService实例
    """
    handler = get_voice_command_handler()
    handler.set_voice_service(service)
