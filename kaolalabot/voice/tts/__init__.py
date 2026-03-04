"""TTS module for text-to-speech synthesis."""

from .tts_interface import TTSStream, TTSAudioChunk, ChunkStrategy
from .tts_edge import EdgeTTSStream, LocalTTSStream

__all__ = ["TTSStream", "TTSAudioChunk", "ChunkStrategy", "EdgeTTSStream", "LocalTTSStream"]
