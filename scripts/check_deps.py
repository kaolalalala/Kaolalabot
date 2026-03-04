#!/usr/bin/env python
import sys
print("Python:", sys.executable)

try:
    import webrtcvad
    print("webrtcvad: OK")
except ImportError as e:
    print("webrtcvad: NOT FOUND -", e)

try:
    import sounddevice
    print("sounddevice: OK")
except ImportError as e:
    print("sounddevice: NOT FOUND -", e)

try:
    import faster_whisper
    print("faster_whisper: OK")
except ImportError as e:
    print("faster_whisper: NOT FOUND -", e)

try:
    import edge_tts
    print("edge_tts: OK")
except ImportError as e:
    print("edge_tts: NOT FOUND -", e)

print("\n=== Testing ASR Model ===")
try:
    from faster_whisper import WhisperModel
    print("Loading tiny model...")
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    print("Model loaded successfully!")
except Exception as e:
    print("Model load error:", e)
