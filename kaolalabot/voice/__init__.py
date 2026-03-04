"""Voice interaction module for kaolalabot.

This module provides a complete voice interaction system with:
- Audio input/output (microphone and speaker)
- Voice Activity Detection (VAD)
- Streaming ASR (Automatic Speech Recognition)
- Streaming TTS (Text-to-Speech)
- Turn management (interrupt/barge-in handling)
- Session FSM (Finite State Machine) for continuous state
- VoiceService for independent service management
- Voice API for web interface integration

Architecture:
    Mic -> VAD -> ASR -> AgentBridge -> TTS -> Speaker
                                    ^
                                    |
                              TurnManager (barge-in)
                              SessionFSM (state)
                              
Usage:
    # 1. 独立语音模式
    from kaolalabot.voice import VoiceService, VoiceConfig
    
    service = VoiceService(config=VoiceConfig())
    await service.start()
    
    # 2. 集成到聊天系统
    from kaolalabot.voice import create_voice_service
    service = await create_voice_service(agent_loop=agent_loop)
    
    # 3. Web API (预留)
    from kaolalabot.voice.api import create_voice_router
    router = create_voice_router(service)
"""

from .session_fsm import SessionState, SessionFSM
from .turn_manager import TurnManager
from .audio_in import AudioIn
from .audio_out import AudioOut
from .vad import VAD, VADEvent, VADEventType
from .asr.asr_interface import ASRStream
from .asr.asr_whisper_window import WhisperWindowASR
from .tts.tts_interface import TTSStream
from .tts.tts_edge import EdgeTTSStream
from .agent.openclaw_bridge import OpenClawBridge
from .agent.agent_interface import AgentBridge
from .shell import VoiceShell, VoiceShellApp, VoiceConfig, create_voice_shell
from .service import VoiceService, VoiceServiceManager, create_voice_service
from .commands import VoiceCommandHandler, handle_voice_command, set_voice_service_for_commands
from .feishu_integration import FeishuVoiceMixin, integrate_voice_to_feishu

__all__ = [
    "SessionState",
    "SessionFSM",
    "TurnManager",
    "AudioIn",
    "AudioOut",
    "VAD",
    "VADEvent",
    "VADEventType",
    "ASRStream",
    "WhisperWindowASR",
    "TTSStream",
    "EdgeTTSStream",
    "OpenClawBridge",
    "AgentBridge",
    "VoiceShell",
    "VoiceShellApp",
    "VoiceConfig",
    "create_voice_shell",
    "VoiceService",
    "VoiceServiceManager",
    "create_voice_service",
    "VoiceCommandHandler",
    "handle_voice_command",
    "set_voice_service_for_commands",
    "FeishuVoiceMixin",
    "integrate_voice_to_feishu",
]
