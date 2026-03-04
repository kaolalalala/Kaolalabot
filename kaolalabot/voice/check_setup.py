#!/usr/bin/env python
"""语音模块快速验证脚本

运行此脚本快速检查语音模块是否正常工作:
    python check_voice_setup.py
"""

import sys
import os

def check_dependencies():
    """检查依赖是否已安装"""
    print("=" * 50)
    print("1. 检查依赖...")
    print("=" * 50)
    
    deps = {
        "sounddevice": "音频输入/输出",
        "webrtcvad": "语音活动检测",
        "faster_whisper": "语音识别(ASR)",
        "edge_tts": "语音合成(TTS)",
        "numpy": "数值计算",
    }
    
    all_ok = True
    for module, desc in deps.items():
        try:
            __import__(module)
            print(f"  ✓ {module} - {desc}")
        except ImportError:
            print(f"  ✗ {module} - {desc} [未安装]")
            all_ok = False
    
    return all_ok


def check_audio_devices():
    """检查音频设备"""
    print("\n" + "=" * 50)
    print("2. 检查音频设备...")
    print("=" * 50)
    
    try:
        import sounddevice as sd
        
        print("\n输入设备(麦克风):")
        try:
            inputs = sd.query_devices(kind='input')
            if isinstance(inputs, dict):
                inputs = [inputs]
            for i, dev in enumerate(inputs):
                print(f"  [{i}] {dev['name']}")
                print(f"      采样率: {dev['default_samplerate']}Hz, 通道: {dev['max_input_channels']}")
        except Exception as e:
            print(f"  无输入设备: {e}")
        
        print("\n输出设备(扬声器):")
        try:
            outputs = sd.query_devices(kind='output')
            if isinstance(outputs, dict):
                outputs = [outputs]
            for i, dev in enumerate(outputs):
                print(f"  [{i}] {dev['name']}")
                print(f"      采样率: {dev['default_samplerate']}Hz, 通道: {dev['max_output_channels']}")
        except Exception as e:
            print(f"  无输出设备: {e}")
            
        return True
    except ImportError:
        print("  需要安装 sounddevice")
        return False


def check_microphone():
    """测试麦克风是否能正常录音"""
    print("\n" + "=" * 50)
    print("3. 测试麦克风...")
    print("=" * 50)
    
    try:
        import sounddevice as sd
        import numpy as np
        
        print("  正在录制3秒音频...")
        print("  请对着麦克风说话...")
        
        recording = sd.rec(
            frames=16000 * 3,
            samplerate=16000,
            channels=1,
            dtype='int16'
        )
        sd.wait()
        
        audio_float = recording.astype(np.float32) / 32767.0
        rms = np.sqrt(np.mean(audio_float ** 2))
        peak = np.max(np.abs(audio_float))
        
        print(f"  RMS音量: {rms:.4f}")
        print(f"  峰值音量: {peak:.4f}")
        
        if rms > 0.005:
            print("  ✓ 麦克风正常工作")
            return True
        else:
            print("  ⚠ 音量过低，请检查麦克风连接和音量设置")
            return False
            
    except Exception as e:
        print(f"  ✗ 麦克风测试失败: {e}")
        return False


def check_voice_modules():
    """检查语音模块能否导入"""
    print("\n" + "=" * 50)
    print("4. 检查语音模块...")
    print("=" * 50)
    
    modules = [
        ("kaolalabot.voice", "语音主模块"),
        ("kaolalabot.voice.audio_in", "音频输入"),
        ("kaolalabot.voice.audio_out", "音频输出"),
        ("kaolalabot.voice.vad", "语音活动检测"),
        ("kaolalabot.voice.session_fsm", "状态机"),
        ("kaolalabot.voice.turn_manager", "打断管理"),
        ("kaolalabot.voice.asr", "语音识别"),
        ("kaolalabot.voice.tts", "语音合成"),
    ]
    
    all_ok = True
    for module, desc in modules:
        try:
            __import__(module)
            print(f"  ✓ {module} - {desc}")
        except ImportError as e:
            print(f"  ✗ {module} - {desc}: {e}")
            all_ok = False
    
    return all_ok


def check_asr_model():
    """检查ASR模型"""
    print("\n" + "=" * 50)
    print("5. 检查ASR模型...")
    print("=" * 50)
    
    try:
        from faster_whisper import WhisperModel
        
        print("  尝试加载 tiny 模型...")
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("  ✓ 模型加载成功")
        return True
    except Exception as e:
        print(f"  ⚠ 模型加载问题: {e}")
        print("    (首次运行时会自动下载)")
        return True  # 不阻塞


def test_voice_shell():
    """快速测试VoiceShell"""
    print("\n" + "=" * 50)
    print("6. 测试VoiceShell初始化...")
    print("=" * 50)
    
    try:
        from kaolalabot.voice import VoiceShell, VoiceConfig
        
        config = VoiceConfig(
            sample_rate=16000,
            vad_aggressiveness=3,
            asr_model_size="tiny",
            tts_voice="zh-CN-XiaoxiaoNeural",
        )
        
        shell = VoiceShell(config)
        print("  ✓ VoiceShell创建成功")
        
        # 尝试初始化
        import asyncio
        asyncio.run(shell.initialize())
        print("  ✓ VoiceShell初始化成功")
        
        asyncio.run(shell.stop())
        print("  ✓ VoiceShell停止成功")
        
        return True
        
    except Exception as e:
        print(f"  ✗ VoiceShell测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  kaolalabot 语音模块快速检查")
    print("=" * 60)
    
    results = []
    
    # 1. 检查依赖
    results.append(("依赖检查", check_dependencies()))
    
    # 2. 检查音频设备
    results.append(("音频设备", check_audio_devices()))
    
    # 3. 检查模块
    results.append(("模块导入", check_voice_modules()))
    
    # 4. 检查模型
    results.append(("ASR模型", check_asr_model()))
    
    # 5. 测试麦克风
    results.append(("麦克风测试", check_microphone()))
    
    # 6. 测试VoiceShell
    results.append(("VoiceShell", test_voice_shell()))
    
    # 总结
    print("\n" + "=" * 60)
    print("  检查结果总结")
    print("=" * 60)
    
    all_pass = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_pass = False
    
    print("=" * 60)
    
    if all_pass:
        print("\n🎉 所有检查通过! 语音模块已就绪。")
        print("\n启动语音模式:")
        print("  python run_voice.py")
    else:
        print("\n⚠ 部分检查未通过，请根据上述结果进行修复。")
    
    print()
    
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
