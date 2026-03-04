#!/usr/bin/env python
"""测试直接加载本地模型"""
import sys
print("Python:", sys.executable)

print("\n=== 测试加载本地ASR模型 ===")
try:
    from faster_whisper import WhisperModel
    
    print("尝试加载本地模型...")
    model = WhisperModel(
        "tiny",
        device="cpu",
        compute_type="int8",
        download_root=None  # 不尝试下载
    )
    
    print("✓ 模型加载成功!")
    print("模型:", model)
    
except Exception as e:
    print(f"✗ 模型加载失败: {e}")
    
print("\n=== 测试语音模块 ===")
try:
    from kaolalabot.voice import VoiceShell, VoiceConfig
    
    config = VoiceConfig(
        sample_rate=16000,
        vad_aggressiveness=3,
        asr_model_size="tiny",
        tts_voice="zh-CN-XiaoxiaoNeural",
    )
    
    shell = VoiceShell(config)
    print("✓ VoiceShell 创建成功")
    
    import asyncio
    asyncio.run(shell.initialize())
    print("✓ VoiceShell 初始化成功")
    
    asyncio.run(shell.stop())
    print("✓ VoiceShell 停止成功")
    
except Exception as e:
    print(f"✗ VoiceShell 失败: {e}")
    import traceback
    traceback.print_exc()
