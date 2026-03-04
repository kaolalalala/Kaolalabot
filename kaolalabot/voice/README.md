# Voice Module

## 功能说明
- 提供语音采集、VAD、ASR、TTS 相关能力。
- `shell.py` 负责本地麦克风交互循环。

## 使用方法
- 在 `config.json` 中启用 `channels.voice.enabled`。
- 设置 `vad_min_silence_duration_ms` 和 `asr_device`。

## 接口定义
- `VoiceShell.initialize()`
- `VoiceShell.start()`
- `VoiceShell.stop()`

## 示例代码
```python
voice = VoiceShell(config)
await voice.initialize()
await voice.start()
```
