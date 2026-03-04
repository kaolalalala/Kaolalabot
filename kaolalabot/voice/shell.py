"""Voice Shell - Main entry point for voice interaction system.

This module integrates all voice components:
- AudioIn: Microphone input
- VAD: Voice Activity Detection
- ASR: Automatic Speech Recognition
- AgentBridge: Connects to kaolalabot agent
- TTS: Text-to-Speech synthesis
- AudioOut: Speaker output
- TurnManager: Barge-in handling
- SessionFSM: State management

The voice flow:
1. AudioIn captures microphone frames
2. VAD detects speech start/end
3. ASR converts audio to text (internal)
4. AgentBridge calls kaolalabot agent with text
5. TTS synthesizes agent response
6. AudioOut plays TTS audio
7. TurnManager handles interruptions
8. SessionFSM manages conversation state
"""

from __future__ import annotations

import asyncio
import signal
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from kaolalabot.voice.audio_in import AudioIn
from kaolalabot.voice.audio_out import AudioOut
from kaolalabot.voice.vad import VAD, VADEventType
from kaolalabot.voice.asr import WhisperWindowASR
from kaolalabot.voice.tts import EdgeTTSStream, ChunkStrategy
from kaolalabot.voice.turn_manager import TurnManager
from kaolalabot.voice.session_fsm import SessionFSM
from kaolalabot.voice.agent import OpenClawBridge


@dataclass
class VoiceConfig:
    """Voice interaction configuration."""

    sample_rate: int = 16000
    frame_duration_ms: int = 20
    channels: int = 1

    vad_aggressiveness: int = 3
    vad_enabled: bool = True
    vad_min_speech_duration_ms: int = 250
    vad_min_silence_duration_ms: int = 500
    vad_speech_timeout_ms: int = 3000
    vad_energy_threshold: float = 500.0

    asr_model_size: str = "tiny"
    asr_language: str = "auto"
    asr_device: str = "auto"
    asr_window_interval_ms: int = 500
    asr_final_silence_ms: int = 1000

    tts_voice: str = "zh-CN-XiaoxiaoNeural"
    tts_rate: str = "+0%"
    tts_max_chars_per_chunk: int = 50
    tts_chunk_interval_ms: int = 800

    turn_manager_enabled: bool = True
    turn_manager_barge_in: bool = True

    fsm_idle_timeout: float = 300.0
    fsm_thinking_timeout: float = 60.0
    fsm_speaking_timeout: float = 120.0


class VoiceShell:
    """
    Main voice shell that orchestrates all voice components.

    This is the central coordinator that connects:
    - Audio input (microphone)
    - Voice Activity Detection
    - Speech Recognition
    - Agent processing
    - Speech Synthesis
    - Audio output (speaker)

    Usage:
        shell = VoiceShell(config, agent_loop)
        await shell.run()
    """

    def __init__(
        self,
        config: VoiceConfig | None = None,
        agent_loop=None,
    ):
        """
        Initialize VoiceShell.

        Args:
            config: Voice configuration
            agent_loop: kaolalabot AgentLoop instance
        """
        self.config = config or VoiceConfig()

        self._audio_in: AudioIn | None = None
        self._audio_out: AudioOut | None = None
        self._vad: VAD | None = None
        self._asr: WhisperWindowASR | None = None
        self._tts: EdgeTTSStream | None = None
        self._turn_manager: TurnManager | None = None
        self._session_fsm: SessionFSM | None = None
        self._agent_bridge: OpenClawBridge | None = None

        self._agent_loop = agent_loop

        self._running = False
        self._main_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        """Initialize all voice components."""
        logger.info("Initializing VoiceShell...")

        self._audio_in = AudioIn(
            sample_rate=self.config.sample_rate,
            frame_duration_ms=self.config.frame_duration_ms,
            channels=self.config.channels,
            backend="sounddevice",
        )

        self._audio_out = AudioOut(
            sample_rate=24000,
            channels=1,
            backend="sounddevice",
        )

        self._vad = VAD(
            sample_rate=self.config.sample_rate,
            aggressiveness=self.config.vad_aggressiveness,
            frame_duration_ms=self.config.frame_duration_ms,
            backend="webrtc",
            min_speech_duration_ms=self.config.vad_min_speech_duration_ms,
            min_silence_duration_ms=self.config.vad_min_silence_duration_ms,
            speech_timeout_ms=self.config.vad_speech_timeout_ms,
            energy_threshold=self.config.vad_energy_threshold,
        )

        self._asr = WhisperWindowASR(
            model_size=self.config.asr_model_size,
            language=self.config.asr_language,
            device=self.config.asr_device,
            sample_rate=self.config.sample_rate,
            window_interval_ms=self.config.asr_window_interval_ms,
            final_silence_ms=self.config.asr_final_silence_ms,
        )

        self._tts = EdgeTTSStream(
            voice=self.config.tts_voice,
            rate=self.config.tts_rate,
            max_chars_per_chunk=self.config.tts_max_chars_per_chunk,
            chunk_interval_ms=self.config.tts_chunk_interval_ms,
        )

        self._turn_manager = TurnManager(
            enabled=self.config.turn_manager_enabled,
            barge_in_on_speech_start=self.config.turn_manager_barge_in,
            interrupt_on_speech_start=self.config.turn_manager_barge_in,
            clear_queue_on_barge_in=True,
        )

        self._session_fsm = SessionFSM(
            idle_timeout_seconds=self.config.fsm_idle_timeout,
            thinking_timeout_seconds=self.config.fsm_thinking_timeout,
            speaking_timeout_seconds=self.config.fsm_speaking_timeout,
        )

        if self._agent_loop:
            self._agent_bridge = OpenClawBridge(
                agent_loop=self._agent_loop,
            )

        self._turn_manager.register_cancel_callback(self._on_barge_in_cancel)
        self._turn_manager.register_queue_clear_callback(self._on_barge_in_clear)

        logger.info("VoiceShell initialized")

    async def _on_barge_in_cancel(self) -> None:
        """Handle barge-in cancellation."""
        if self._tts:
            await self._tts.stop()
            await self._tts.start()
        if self._audio_out:
            await self._audio_out.flush()
        if self._agent_bridge:
            await self._agent_bridge.cancel()
        if self._asr:
            self._asr.reset()

    async def _on_barge_in_clear(self) -> None:
        """Handle barge-in queue clearing."""
        if self._audio_out:
            await self._audio_out.flush()

    async def start(self) -> None:
        """Start the voice shell."""
        if self._running:
            return

        if not all(
            [
                self._audio_in,
                self._audio_out,
                self._vad,
                self._asr,
                self._tts,
                self._turn_manager,
                self._session_fsm,
            ]
        ):
            await self.initialize()
        await self._audio_in.start()
        await self._audio_out.start()
        await self._asr.start()
        await self._tts.start()
        if self._agent_bridge:
            await self._agent_bridge.start()

        self._running = True
        if not self._main_task or self._main_task.done():
            self._main_task = asyncio.create_task(self._voice_loop())
        logger.info("VoiceShell started")

    async def stop(self) -> None:
        """Stop the voice shell."""
        self._running = False

        if self._main_task and not self._main_task.done():
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass

        if self._audio_in:
            await self._audio_in.stop()
        if self._audio_out:
            await self._audio_out.stop()
        if self._asr:
            await self._asr.stop()
        if self._tts:
            await self._tts.stop()
        if self._agent_bridge:
            await self._agent_bridge.stop()

        logger.info("VoiceShell stopped")

    async def _voice_loop(self) -> None:
        """Run VAD + ASR processing loop."""
        speech_task: asyncio.Task | None = None

        try:
            async for frame in self._audio_in.frames():
                if not self._running:
                    break

                event = self._vad.process(frame.data)
                if not event:
                    await asyncio.sleep(0.001)
                    continue

                if event.event_type == VADEventType.SPEECH_START:
                    if self._session_fsm.is_speaking() or self._session_fsm.is_thinking():
                        logger.info("VAD: speech during agent response, checking barge-in")
                        if self._turn_manager.should_barge_in():
                            await self._turn_manager.barge_in()
                            await self._session_fsm.go_idle()
                            logger.info("Barge-in triggered")

                    if not self._session_fsm.is_listening():
                        logger.info("Detected speech start, entering listening state")
                        await self._session_fsm.start_listening()
                    self._turn_manager.set_user_speaking(True)

                if self._session_fsm.is_listening():
                    await self._asr.push_audio(frame.data)

                if event.event_type == VADEventType.SPEECH_END and self._session_fsm.is_listening():
                    logger.info("VAD: speech ended, finalizing ASR")
                    self._turn_manager.set_user_speaking(False)

                    if speech_task and not speech_task.done():
                        speech_task.cancel()
                        try:
                            await speech_task
                        except asyncio.CancelledError:
                            pass
                    speech_task = asyncio.create_task(self._process_user_speech())

                await asyncio.sleep(0.001)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Voice loop error: {}", e)

    async def run(self) -> None:
        """Run the voice shell main loop."""
        await self.start()
        try:
            await self._main_task
        except asyncio.CancelledError:
            pass

    async def _process_user_speech(self) -> None:
        """Process user speech after speech end detected."""
        try:
            await asyncio.sleep(0.1)

            final_text = await self._asr.finalize()

            if final_text and final_text.strip():
                logger.info("User said: {}", final_text)

                await self._session_fsm.start_thinking(final_text)
                self._turn_manager.set_agent_thinking(True)

                response_text = await self._get_agent_response(final_text)

                self._turn_manager.set_agent_thinking(False)

                if response_text:
                    await self._session_fsm.start_speaking(response_text)
                    self._turn_manager.set_agent_speaking(True)

                    await self._speak_response(response_text)

                    self._turn_manager.set_agent_speaking(False)
                    await self._session_fsm.go_idle()
                else:
                    await self._session_fsm.go_idle()
            else:
                logger.info("ASR produced empty result, returning to idle")
                await self._session_fsm.go_idle()

            self._asr.reset()
            self._vad.reset()
            self._turn_manager.set_user_speaking(False)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Error processing user speech: {}", e)
            await self._session_fsm.go_idle()

    async def _get_agent_response(self, query: str) -> str | None:
        """Get response from agent."""
        if not self._agent_bridge:
            return "抱歉，语音服务尚未配置 Agent。"

        try:
            response_text = ""

            async for token in self._agent_bridge.run(query):
                if not self._running:
                    break
                response_text += token.text

            return response_text

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Agent error: {}", e)
            return "抱歉，处理你的请求时发生错误。"

    async def _speak_response(self, text: str) -> None:
        """Speak the agent response using TTS."""

        async def text_chunks():
            async for chunk in ChunkStrategy.split_into_chunks(text):
                if not self._running:
                    break
                yield chunk

        try:
            async for audio_chunk in self._tts.speak_stream(text_chunks()):
                if not self._running:
                    break
                await self._audio_out.play_chunk(audio_chunk.data)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("TTS error: {}", e)

    def get_status(self) -> dict:
        """Get current voice shell status."""
        return {
            "running": self._running,
            "state": self._session_fsm.state.value if self._session_fsm else "unknown",
            "state_description": (
                self._session_fsm.get_state_description()
                if self._session_fsm
                else "鏈垵濮嬪寲"
            ),
        }


class VoiceShellApp:
    """
    Application wrapper for VoiceShell with signal handling.
    """

    def __init__(
        self,
        config: VoiceConfig | None = None,
        agent_loop=None,
    ):
        self.shell = VoiceShell(config, agent_loop)
        self._shutdown_event = asyncio.Event()

    async def run(self) -> None:
        """Run the voice shell application."""
        loop = asyncio.get_event_loop()

        def handle_signal(sig):
            logger.info("Received signal {}, shutting down...", sig)
            asyncio.create_task(self.shutdown())

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))
            except NotImplementedError:
                pass

        try:
            await self.shell.run()
        except Exception as e:
            logger.error("VoiceShell error: {}", e)
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Shutdown the application."""
        if not self._shutdown_event.is_set():
            self._shutdown_event.set()
            await self.shell.stop()


async def create_voice_shell(
    config_path: Path | None = None,
    agent_loop=None,
) -> VoiceShell:
    """
    Create and initialize a VoiceShell instance.

    Args:
        config_path: Optional path to config file
        agent_loop: kaolalabot AgentLoop instance

    Returns:
        Initialized VoiceShell
    """
    import yaml

    config = VoiceConfig()

    if config_path and config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f)
            if data and "voice" in data:
                voice_cfg = data["voice"]
                config.sample_rate = voice_cfg.get("sample_rate", config.sample_rate)
                config.frame_duration_ms = voice_cfg.get("frame_duration_ms", config.frame_duration_ms)
                config.channels = voice_cfg.get("channels", config.channels)

            if data and "vad" in data:
                vad_cfg = data["vad"]
                config.vad_aggressiveness = vad_cfg.get("aggressiveness", config.vad_aggressiveness)
                config.vad_enabled = vad_cfg.get("enabled", config.vad_enabled)
                config.vad_min_speech_duration_ms = vad_cfg.get(
                    "min_speech_duration_ms",
                    config.vad_min_speech_duration_ms,
                )
                config.vad_min_silence_duration_ms = vad_cfg.get(
                    "min_silence_duration_ms",
                    config.vad_min_silence_duration_ms,
                )
                config.vad_speech_timeout_ms = vad_cfg.get(
                    "speech_timeout_ms",
                    config.vad_speech_timeout_ms,
                )
                config.vad_energy_threshold = vad_cfg.get(
                    "energy_threshold",
                    config.vad_energy_threshold,
                )

            if data and "asr" in data:
                asr_cfg = data["asr"]
                config.asr_model_size = asr_cfg.get("model_size", config.asr_model_size)
                config.asr_language = asr_cfg.get("language", config.asr_language)
                config.asr_device = asr_cfg.get("device", config.asr_device)
                config.asr_window_interval_ms = asr_cfg.get("window_interval_ms", config.asr_window_interval_ms)
                config.asr_final_silence_ms = asr_cfg.get("final_silence_ms", config.asr_final_silence_ms)

            if data and "tts" in data:
                tts_cfg = data["tts"]
                config.tts_voice = tts_cfg.get("voice", config.tts_voice)
                config.tts_rate = tts_cfg.get("rate", config.tts_rate)
                config.tts_max_chars_per_chunk = tts_cfg.get("max_chars_per_chunk", config.tts_max_chars_per_chunk)
                config.tts_chunk_interval_ms = tts_cfg.get("chunk_interval_ms", config.tts_chunk_interval_ms)

    shell = VoiceShell(config, agent_loop)
    await shell.initialize()

    return shell

