"""Whisper-based ASR with windowed pseudo-streaming.

This module implements a "pseudo-streaming" ASR using faster-whisper:
- Audio is accumulated in windows (e.g., 0.5s)
- Each window is transcribed incrementally
- Partial results are shown during speaking
- Final results are produced after silence detection
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import numpy as np
from loguru import logger

from .asr_interface import ASRStream, ASREventHandler, ASRResult


class WhisperWindowASR(ASRStream):
    """
    Whisper-based ASR with windowed pseudo-streaming.

    Uses faster-whisper for efficient transcription with:
    - Rolling window inference (every N ms)
    - Incremental text拼接 (partial results)
    - Silence-based finalization

    This is an MVP implementation that balances simplicity with
    reasonable streaming performance.
    """

    def __init__(
        self,
        model_size: str = "tiny",
        language: str = "auto",
        compute_type: str = "int8",
        sample_rate: int = 16000,
        window_interval_ms: int = 500,
        final_silence_ms: int = 1000,
        device: str = "auto",
    ):
        """
        Initialize Whisper ASR.

        Args:
            model_size: Whisper model size ('tiny', 'base', 'small', 'medium', 'large')
            language: Language code or 'auto' for detection
            compute_type: Computation type ('int8', 'int8_float16', 'float16', 'float32')
            sample_rate: Audio sample rate
            window_interval_ms: Interval between inference calls
            final_silence_ms: Silence duration to trigger finalization
            device: Device to use ('auto', 'cpu', 'cuda')
        """
        self.model_size = model_size
        self.language = language
        self.compute_type = compute_type
        self.sample_rate = sample_rate
        self.window_interval_ms = window_interval_ms
        self.final_silence_ms = final_silence_ms
        self.device = device

        self._model = None
        self._running = False
        self._audio_buffer: list[np.ndarray] = []
        self._buffer_duration_ms = 0
        self._last_inference_ms = 0
        self._silence_duration_ms = 0
        self._last_text = ""
        self._final_text = ""
        self._event_handler: ASREventHandler | None = None
        self._lock = asyncio.Lock()
        self._cpu_fallback_done = False

        self._window_samples = int(sample_rate * window_interval_ms / 1000)
        self._final_silence_samples = int(sample_rate * final_silence_ms / 1000)

    async def start(self) -> None:
        """Start the ASR and load model."""
        if self._running:
            return

        self._running = True

        try:
            await asyncio.to_thread(self._load_model)
        except Exception as e:
            if not await self._fallback_to_cpu_on_error(e):
                raise

    def _load_model(self) -> None:
        """Load Whisper model in background thread."""
        try:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        except ImportError:
            raise RuntimeError(
                "faster-whisper not installed. Install with: pip install faster-whisper"
            )
        except Exception as e:
            if "Unable to open file" in str(e) or "download" in str(e).lower():
                raise RuntimeError(
                    f"ASR模型下载失败: {e}\n"
                    "解决方法:\n"
                    "1. 检查网络连接\n"
                    "2. 设置镜像: set HF_ENDPOINT=https://hf-mirror.com\n"
                    "3. 或手动下载模型: https://huggingface.co/Systran/faster-whisper-tiny"
                )
            raise

    def _load_model_cpu(self) -> None:
        """Force reload model on CPU backend."""
        from faster_whisper import WhisperModel

        self.device = "cpu"
        self.compute_type = "int8"
        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )

    @staticmethod
    def _is_cuda_runtime_error(error: Exception) -> bool:
        message = str(error).lower()
        keywords = (
            "cublas",
            "cuda",
            "cudnn",
            "cudart",
            "dll is not found",
            "cannot be loaded",
            "libcublas",
        )
        return any(keyword in message for keyword in keywords)

    async def _fallback_to_cpu_on_error(self, error: Exception) -> bool:
        """Fallback to CPU model once when CUDA runtime is unavailable."""
        if self.device == "cpu" or self._cpu_fallback_done:
            return False
        if not self._is_cuda_runtime_error(error):
            return False

        self._cpu_fallback_done = True
        logger.warning("ASR CUDA runtime unavailable ({}), switching to CPU.", error)

        try:
            await asyncio.to_thread(self._load_model_cpu)
            logger.info("ASR CPU fallback active")
            return True
        except Exception as cpu_error:
            logger.error("ASR CPU fallback failed: {}", cpu_error)
            return False

    async def stop(self) -> None:
        """Stop the ASR."""
        self._running = False
        if self._model:
            del self._model
            self._model = None

    def set_event_handler(self, handler: ASREventHandler) -> None:
        """Set the event handler for ASR results."""
        self._event_handler = handler

    async def push_audio(self, audio_data: np.ndarray) -> None:
        """Push audio data to the buffer."""
        if not self._running:
            return

        # faster-whisper expects float32 PCM in [-1, 1].
        if audio_data.dtype == np.int16:
            audio_data = audio_data.astype(np.float32) / 32768.0
        elif audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
        if audio_data.size and np.max(np.abs(audio_data)) > 1.0:
            audio_data = audio_data / 32768.0

        async with self._lock:
            self._audio_buffer.append(audio_data)
            self._buffer_duration_ms += len(audio_data) * 1000 // self.sample_rate

            if self._buffer_duration_ms >= self.window_interval_ms:
                await self._process_window()

    async def _process_window(self) -> None:
        """Process accumulated audio buffer."""
        if not self._model or len(self._audio_buffer) == 0:
            return

        audio_data = np.concatenate(self._audio_buffer)
        self._audio_buffer = []
        self._buffer_duration_ms = 0

        def transcribe():
            segments, _ = self._model.transcribe(
                audio_data,
                language=self.language if self.language != "auto" else None,
                beam_size=1,
                vad_filter=False,
                initial_prompt=None,
            )
            return " ".join(segment.text for segment in segments)

        try:
            text = await asyncio.to_thread(transcribe)
        except Exception as e:
            if await self._fallback_to_cpu_on_error(e):
                try:
                    text = await asyncio.to_thread(transcribe)
                except Exception as retry_error:
                    logger.debug("ASR window transcribe failed after CPU fallback: {}", retry_error)
                    return
            else:
                logger.debug("ASR window transcribe failed: {}", e)
                return

        if text.strip():
            self._silence_duration_ms = 0
            self._last_text = text

            if self._event_handler:
                await self._event_handler.handle_partial(text)
        else:
            self._silence_duration_ms += self.window_interval_ms

            if self._silence_duration_ms >= self.final_silence_ms and self._last_text:
                await self.finalize()

    async def finalize(self) -> str | None:
        """Force finalization and return final text."""
        async with self._lock:
            if self._audio_buffer and self._model:
                audio_data = np.concatenate(self._audio_buffer)

                def transcribe():
                    segments, _ = self._model.transcribe(
                        audio_data,
                        language=self.language if self.language != "auto" else None,
                    )
                    return " ".join(segment.text for segment in segments)

                try:
                    final_text = await asyncio.to_thread(transcribe)
                    if final_text.strip():
                        self._final_text = final_text
                        if self._event_handler:
                            await self._event_handler.handle_final(final_text)
                except Exception as e:
                    if await self._fallback_to_cpu_on_error(e):
                        try:
                            final_text = await asyncio.to_thread(transcribe)
                            if final_text.strip():
                                self._final_text = final_text
                                if self._event_handler:
                                    await self._event_handler.handle_final(final_text)
                        except Exception as retry_error:
                            logger.debug("ASR finalize failed after CPU fallback: {}", retry_error)
                            final_text = self._last_text
                    else:
                        logger.debug("ASR finalize transcribe failed: {}", e)
                        final_text = self._last_text

            result = self._final_text or self._last_text
            self.reset()
            return result

    def reset(self) -> None:
        """Reset ASR state."""
        self._audio_buffer = []
        self._buffer_duration_ms = 0
        self._last_inference_ms = 0
        self._silence_duration_ms = 0
        self._last_text = ""
        self._final_text = ""

    @property
    def is_running(self) -> bool:
        """Check if ASR is running."""
        return self._running


class VoskASR(ASRStream):
    """
    Vosk-based ASR for lightweight streaming recognition.

    Vosk provides fast, low-latency streaming ASR suitable for
    real-time applications.
    """

    def __init__(
        self,
        model_path: str = "model",
        sample_rate: int = 16000,
    ):
        """
        Initialize Vosk ASR.

        Args:
            model_path: Path to Vosk model directory
            sample_rate: Audio sample rate
        """
        self.model_path = model_path
        self.sample_rate = sample_rate

        self._model = None
        self._recognizer = None
        self._running = False
        self._final_text = ""
        self._event_handler: ASREventHandler | None = None

    async def start(self) -> None:
        """Start the ASR and load model."""
        if self._running:
            return

        try:
            from vosk import Model, KaldiRecognizer

            self._model = Model(self.model_path)
            self._recognizer = KaldiRecognizer(self._model, self.sample_rate)
            self._running = True
        except ImportError:
            raise RuntimeError(
                "vosk not installed. Install with: pip install vosk\n"
                "Download model from: https://alphacephei.com/vosk/models"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load Vosk model: {e}")

    async def stop(self) -> None:
        """Stop the ASR."""
        self._running = False
        self._model = None
        self._recognizer = None

    def set_event_handler(self, handler: ASREventHandler) -> None:
        """Set the event handler for ASR results."""
        self._event_handler = handler

    async def push_audio(self, audio_data: np.ndarray) -> None:
        """Push audio data for recognition."""
        if not self._running or not self._recognizer:
            return

        if audio_data.dtype != np.int16:
            audio_data = (audio_data * 32767).astype(np.int16)

        audio_bytes = audio_data.tobytes()
        self._recognizer.AcceptWaveform(audio_bytes)

        result = self._recognizer.PartialResult()
        if self._event_handler and "partial" in result:
            partial_text = result["partial"]
            await self._event_handler.handle_partial(partial_text)

    async def finalize(self) -> str | None:
        """Force finalization and return final text."""
        if self._recognizer:
            result = self._recognizer.FinalResult()
            if "text" in result:
                self._final_text = result["text"]
                if self._event_handler:
                    await self._event_handler.handle_final(self._final_text)

        self.reset()
        return self._final_text

    def reset(self) -> None:
        """Reset ASR state."""
        if self._recognizer:
            self._recognizer.Reset()
        self._final_text = ""

    @property
    def is_running(self) -> bool:
        """Check if ASR is running."""
        return self._running
