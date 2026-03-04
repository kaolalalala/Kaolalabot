#!/usr/bin/env python
"""语音模块诊断脚本 - 帮助排查无响应问题"""

import asyncio
import sys

async def main():
    print("=" * 60)
    print("🔍 语音模块诊断")
    print("=" * 60)
    
    # 1. 检查依赖
    print("\n[1] 检查依赖...")
    try:
        import sounddevice as sd
        print(f"  ✓ sounddevice: {sd.__version__}")
    except ImportError as e:
        print(f"  ✗ sounddevice: {e}")
    
    try:
        import webrtcvad
        print(f"  ✓ webrtcvad: 已安装")
    except ImportError as e:
        print(f"  ✗ webrtcvad: {e}")
    
    try:
        import faster_whisper
        print(f"  ✓ faster-whisper: 已安装")
    except ImportError as e:
        print(f"  ✗ faster-whisper: {e}")
    
    try:
        import edge_tts
        print(f"  ✓ edge-tts: 已安装")
    except ImportError as e:
        print(f"  ✗ edge-tts: {e}")

    # 2. 检查音频设备
    print("\n[2] 检查音频设备...")
    try:
        import sounddevice as sd
        inputs = sd.query_devices(kind='input')
        outputs = sd.query_devices(kind='output')
        
        print(f"  输入设备: {inputs['name'] if isinstance(inputs, dict) else '未找到'}")
        print(f"  输出设备: {outputs['name'] if isinstance(outputs, dict) else '未找到'}")
        
        # 测试录音
        print("\n[3] 测试麦克风录音...")
        print("  正在录制3秒，请对着麦克风说话...")
        
        recording = sd.rec(
            frames=16000 * 3,
            samplerate=16000,
            channels=1,
            dtype='int16'
        )
        sd.wait()
        
        import numpy as np
        audio_float = recording.astype(np.float32) / 32767.0
        rms = np.sqrt(np.mean(audio_float ** 2))
        
        print(f"  录音完成!")
        print(f"  RMS音量: {rms:.4f}")
        
        if rms > 0.01:
            print("  ✓ 麦克风正常工作")
        else:
            print("  ⚠ 麦克风音量过低，可能无法被VAD检测到")
            print("     请靠近麦克风或调高系统麦克风音量")
            
    except Exception as e:
        print(f"  ✗ 音频设备测试失败: {e}")
        import traceback
        traceback.print_exc()

    # 4. 检查VAD
    print("\n[4] 测试VAD...")
    try:
        from kaolalabot.voice import VAD
        
        vad = VAD(sample_rate=16000, aggressiveness=3)
        
        # 使用刚才录制的音频测试
        if 'recording' in dir():
            event = vad.process(recording[:, 0])
            if event:
                print(f"  ✓ VAD检测到语音: {event.event_type}")
            else:
                print("  ⚠ VAD未检测到语音 (可能是静音)")
        else:
            print("  ⚠ 无录音数据，跳过VAD测试")
            
    except Exception as e:
        print(f"  ✗ VAD测试失败: {e}")

    # 5. 检查ASR模型
    print("\n[5] 检查ASR模型...")
    try:
        from faster_whisper import WhisperModel
        print("  尝试加载模型...")
        
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("  ✓ 模型加载成功")
        
        # 测试识别
        if 'recording' in dir() and rms > 0.01:
            print("  尝试识别刚才的录音...")
            import tempfile
            import soundfile as sf
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                sf.write(f.name, recording, 16000)
                segments, info = model.transcribe(f.name, language="zh")
                text = " ".join([s.text for s in segments])
                print(f"  识别结果: '{text}'")
                
    except Exception as e:
        print(f"  ✗ ASR测试失败: {e}")

    print("\n" + "=" * 60)
    print("诊断完成!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
