# 语音模块接入指南

本指南将帮助你配置并启用kaolalabot的语音交互模块。

## 目录
1. [前置要求](#前置要求)
2. [软件配置](#软件配置)
3. [硬件连接](#硬件连接)
4. [权限设置](#权限设置)
5. [启动语音模式](#启动语音模式)
6. [验证方法](#验证方法)
7. [常见问题](#常见问题)

---

## 前置要求

### 硬件要求
- **麦克风**: USB麦克风或3.5mm耳机麦克风
- **扬声器**: 内置扬声器或外部音箱
- **推荐配置**: 
  - 采样率: 16kHz
  - 单声道 (mono)
  - 16位深度的PCM格式

### 软件要求
- Python 3.10+
- 操作系统: Windows 10+/macOS/Linux

---

## 软件配置

### 1. 安装依赖

```bash
# 安装语音模块所需依赖
pip install sounddevice webrtcvad faster-whisper edge-tts numpy

# 或使用项目依赖文件
pip install -r requirements-backend.txt
```

### 2. 配置检查

确认以下依赖已安装:

```bash
# 验证依赖
python -c "import sounddevice; print('sounddevice:', sounddevice.__version__)"
python -c "import webrtcvad; print('webrtcvad:', webrtcvad.__version__)"
python -c "import faster_whisper; print('faster_whisper installed')"
python -c "import edge_tts; print('edge_tts:', edge_tts.__version__)"
```

### 3. 下载ASR模型

首次运行时会自动下载Whisper模型。若需预下载:

```python
from faster_whisper import WhisperModel

# tiny模型 (~39MB) - 推荐用于测试
model = WhisperModel("tiny", device="cpu", compute_type="int8")

# base模型 (~74MB) - 平衡速度和准确性
model = WhisperModel("base", device="cpu", compute_type="int8")

# small模型 (~244MB) - 更好的准确性
model = WhisperModel("small", device="cpu", compute_type="int8")
```

### 4. 配置文件

编辑 `kaolalabot/voice/config.yaml`:

```yaml
voice:
  enabled: true
  sample_rate: 16000
  frame_duration_ms: 20
  channels: 1

vad:
  enabled: true
  aggressiveness: 3  # 0-3, 越高越敏感

asr:
  provider: whisper
  model_size: tiny   # tiny/base/small/medium
  language: auto     # auto或指定语言代码如zh
  compute_type: int8

tts:
  provider: edge
  voice: zh-CN-XiaoxiaoNeural  # 中文女声
  # 其他可选声音:
  # zh-CN-YunxiNeural - 中文男声
  # zh-CN-XiaoxiaoNeural - 中文女声(推荐)
  rate: "+0%"
  max_chars_per_chunk: 50

turn_manager:
  enabled: true
  barge_in_on_speech_start: true
  interrupt_on_speech_start: true
```

---

## 硬件连接

### Windows
1. **连接麦克风**
   - USB麦克风: 插入USB端口，系统自动识别
   - 3.5mm麦克风: 插入麦克风专用接口(粉色)

2. **设置默认设备**
   ```
   设置 → 声音 → 输入设备 → 选择麦克风
   测试麦克风确保音量 > 50%
   ```

3. **设置扬声器**
   ```
   设置 → 声音 → 输出设备 → 选择扬声器
   调整音量适中
   ```

### macOS
1. **连接麦克风**
   - 插入USB或3.5mm麦克风

2. **设置默认设备**
   ```
   系统偏好设置 → 声音 → 输入/输出
   选择对应的麦克风和扬声器
   ```

### Linux (Ubuntu/Debian)
```bash
# 查看音频设备
pactl list short sources
pactl list short sinks

# 设置默认设备
pactl set-default-source alsa_input.usb-xxx
pactl set-default-sink alsa_output.xxx
```

---

## 权限设置

### Windows
通常自动获取权限。如遇问题:
```
设置 → 隐私 → 麦克风 → 允许应用访问麦克风
```

### macOS
```bash
# 首次运行时会提示授权麦克风
# 若未授权:
系统偏好设置 → 安全性与隐私 → 隐私 → 麦克风
添加Python或终端到允许列表
```

### Linux
```bash
# 添加当前用户到audio组
sudo usermod -a -G audio $USER

# 重新登录后生效
# 或使用pulseaudio时确保有权限
```

---

## 启动语音模式

### 方式1: Python代码启动

```python
import asyncio
from kaolalabot.voice import VoiceShell, VoiceConfig, create_voice_shell
from pathlib import Path

async def main():
    # 方式A: 使用配置文件
    config_path = Path("kaolalabot/voice/config.yaml")
    shell = await create_voice_shell(config_path)
    
    # 方式B: 手动配置
    config = VoiceConfig(
        enabled=True,
        sample_rate=16000,
        vad_aggressiveness=3,
        asr_model_size="tiny",
        tts_voice="zh-CN-XiaoxiaoNeural",
    )
    shell = VoiceShell(config)
    
    # 运行语音交互
    await shell.run()

if __name__ == "__main__":
    asyncio.run(main())
```

### 方式2: 集成到AgentLoop

```python
from kaolalabot.agent.loop import AgentLoop
from kaolalabot.voice import VoiceShell, VoiceConfig
from kaolalabot.config import load_config

# 加载配置
config = load_config("config.json")

# 创建AgentLoop
agent_loop = AgentLoop(config=config)

# 创建VoiceShell并传入AgentLoop
voice_config = VoiceConfig(
    enabled=True,
    vad_aggressiveness=3,
    tts_voice="zh-CN-XiaoxiaoNeural",
)

voice_shell = VoiceShell(voice_config, agent_loop=agent_loop)

# 同时运行
async def run_both():
    # 启动语音处理任务
    voice_task = asyncio.create_task(voice_shell.run())
    
    # 保持主进程运行
    await asyncio.Event().wait()

asyncio.run(run_both())
```

### 方式3: 快捷启动脚本

创建 `run_voice.py`:

```python
#!/usr/bin/env python
"""语音模式启动脚本"""

import asyncio
import signal
import sys
from pathlib import Path

from kaolalabot.voice import VoiceShell, VoiceConfig
from kaolalabot.config import load_config


async def main():
    # 加载配置
    config_path = Path("config.json")
    if config_path.exists():
        config = load_config(config_path)
    else:
        config = None
    
    # 创建语音配置
    voice_config = VoiceConfig(
        enabled=True,
        sample_rate=16000,
        vad_aggressiveness=3,
        asr_model_size="tiny",
        asr_language="auto",
        tts_voice="zh-CN-XiaoxiaoNeural",
        tts_rate="+0%",
    )
    
    # 创建语音外壳
    shell = VoiceShell(voice_config)
    
    # 设置信号处理
    loop = asyncio.get_event_loop()
    
    def signal_handler(sig):
        print("\n正在关闭语音模块...")
        asyncio.create_task(shell.stop())
    
    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(s, lambda: signal_handler(s))
        except NotImplementedError:
            pass
    
    # 启动
    print("=" * 50)
    print("kaolalabot 语音模式")
    print("=" * 50)
    print("按 Ctrl+C 退出")
    print("=" * 50)
    
    try:
        await shell.run()
    except KeyboardInterrupt:
        pass
    finally:
        await shell.stop()
        print("语音模块已关闭")


if __name__ == "__main__":
    asyncio.run(main())
```

运行:
```bash
python run_voice.py
```

---

## 验证方法

### 1. 模块导入测试
```python
# 验证所有模块可导入
python -c "
from kaolalabot.voice import (
    VoiceShell, AudioIn, AudioOut, VAD,
    SessionFSM, TurnManager, EdgeTTSStream, WhisperWindowASR
)
print('所有模块导入成功!')
"
```

### 2. 音频设备检测
```python
import sounddevice as sd

# 列出所有音频设备
print("可用输入设备:")
for i, device in enumerate(sd.query_devices(kind='input')):
    print(f"  {i}: {device['name']}")

print("\n可用输出设备:")
for i, device in enumerate(sd.query_devices(kind='output')):
    print(f"  {i}: {device['name']}")
```

### 3. 麦克风测试
```python
import sounddevice as sd
import numpy as np

# 录制3秒测试音频
print("请说话，录制3秒...")
recording = sd.rec(
    frames=16000 * 3,  # 3秒
    samplerate=16000,
    channels=1,
    dtype='int16'
)
sd.wait()
print(f"录制完成! 音频形状: {recording.shape}")

# 检查音量
audio_float = recording.astype(np.float32) / 32767.0
rms = np.sqrt(np.mean(audio_float ** 2))
print(f"RMS音量: {rms:.4f}")

if rms > 0.01:
    print("✓ 麦克风正常工作")
else:
    print("✗ 麦克风音量过低，请检查连接")
```

### 4. 完整流程测试

```python
import asyncio
from kaolalabot.voice import VoiceConfig

async def test_full_flow():
    config = VoiceConfig(
        enabled=True,
        sample_rate=16000,
        vad_aggressiveness=3,
        asr_model_size="tiny",
    )
    
    # 初始化组件
    from kaolalabot.voice import AudioIn, VAD
    
    audio_in = AudioIn(sample_rate=16000)
    vad = VAD(sample_rate=16000, aggressiveness=3)
    
    print("启动音频采集...")
    await audio_in.start()
    
    print("开始监听(请说话)...")
    print("听到声音后会自动识别...")
    
    async for frame in audio_in.frames():
        event = vad.process(frame.data)
        if event:
            print(f"VAD事件: {event.event_type.value}")
    
    await audio_in.stop()

asyncio.run(test_full_flow())
```

---

## 常见问题

### Q1: 找不到音频设备
```
错误: python - sounddevice: No default input device available
解决:
1. 检查麦克风是否已连接
2. 在系统设置中确认默认设备
3. 指定设备索引: AudioIn(device=0)
```

### Q2: VAD不灵敏
```
解决:
- 降低aggressiveness: VAD(aggressiveness=2)
- 或使用Energy VAD: VAD(backend='energy')
```

### Q3: ASR识别效果差
```
解决:
1. 使用更大的模型: model_size="base"或"small"
2. 指定语言: language="zh"
3. 确保环境安静
4. 麦克风质量要好
```

### Q4: TTS没有声音
```
解决:
1. 检查扬声器是否静音
2. 确认系统音量
3. 使用AudioOut测试播放
```

### Q5: 延迟过高
```
优化建议:
1. 使用更小的ASR模型: tiny
2. 减少TTS chunk大小
3. 使用本地TTS替代Edge TTS
4. 关闭不必要的日志输出
```

### Q6: 打断功能不工作
```
确认:
1. turn_manager.barge_in_on_speech_start = True
2. 麦克风能检测到声音
3. VAD aggressiveness设置合适
```

---

## 性能优化建议

| 场景 | 推荐配置 |
|------|----------|
| 低延迟优先 | ASR: tiny, TTS: edge |
| 准确性优先 | ASR: small, TTS: edge |
| 离线使用 | ASR: tiny, 本地TTS(CosyVoice) |
| 生产环境 | ASR: base, 多路VAD |

---

## 下一步

- 测试通过后，可集成到完整的AgentLoop
- 配置WebSocket实现远程语音控制
- 添加语音命令自定义功能
