#!/usr/bin/env python
"""语音模块详细调试脚本"""

import asyncio
import sys
import numpy as np

async def main():
    print("=" * 60)
    print("🔍 详细调试 - 按 Ctrl+C 退出")
    print("=" * 60)
    
    from kaolalabot.voice import AudioIn, VAD, VoiceConfig
    
    config = VoiceConfig()
    config.vad_aggressiveness = 1
    
    print("\n[1] 初始化组件...")
    
    audio_in = AudioIn(
        sample_rate=config.sample_rate,
        frame_duration_ms=config.frame_duration_ms,
        channels=config.channels,
        backend="sounddevice",
    )
    
    vad = VAD(
        sample_rate=config.sample_rate,
        aggressiveness=config.vad_aggressiveness,
        backend="webrtc",
    )
    
    print(f"    麦克风 sample_rate: {audio_in.sample_rate}")
    print(f"    麦克风 channels: {audio_in.channels}")
    print(f"    VAD aggressiveness: {vad.aggressiveness}")
    
    print("\n[2] 启动音频采集...")
    await audio_in.start()
    print("    ✓ 音频采集已启动")
    
    print("\n[3] 开始监听... (请说话)")
    print("    等待检测到语音...")
    print("-" * 60)
    
    speech_detected = False
    frame_count = 0
    max_frames = 300  # 30秒超时
    
    try:
        async for frame in audio_in.frames():
            frame_count += 1
            
            if frame_count % 50 == 0:
                # 每50帧打印一次状态
                print(f"    帧 {frame_count}: 等待中... (RMS: {np.sqrt(np.mean(frame.astype(np.float32)**2)):.4f})")
            
            event = vad.process(frame.data)
            
            if event:
                print(f"\n    ✓ VAD事件: {event.event_type}")
                print(f"      帧位置: {frame_count}")
                speech_detected = True
                break
            
            if frame_count >= max_frames:
                print("\n    ✗ 超时 (30秒内未检测到语音)")
                break
                
    except KeyboardInterrupt:
        print("\n\n用户中断")
    finally:
        await audio_in.stop()
        print("\n已停止")
    
    if not speech_detected:
        print("\n" + "=" * 60)
        print("问题排查:")
        print("=" * 60)
        print("1. 请确认麦克风音量已调高 (80-100%)")
        print("2. 请确认在安静环境下测试")
        print("3. 请确认麦克风是默认输入设备")

if __name__ == "__main__":
    asyncio.run(main())
