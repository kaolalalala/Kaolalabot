#!/usr/bin/env python
"""超简单测试脚本 - 实时显示VAD状态"""

import asyncio
import sys

async def main():
    print("=" * 50)
    print("语音检测测试")
    print("=" * 50)
    print("请对着麦克风说话...")
    print("-" * 50)
    
    from kaolalabot.voice import AudioIn, VAD
    import numpy as np
    
    audio = AudioIn(sample_rate=16000, backend="sounddevice")
    vad = VAD(sample_rate=16000, aggressiveness=1)
    
    await audio.start()
    print("✓ 已开始监听")
    
    frame_count = 0
    speech_frames = 0
    
    try:
        async for frame in audio.frames():
            frame_count += 1
            
            # 检测语音
            event = vad.process(frame.data)
            
            if event:
                print(f"帧{frame_count}: 检测到 {event.event_type}")
                speech_frames += 1
            elif frame_count % 100 == 0:
                print(f"帧{frame_count}: 等待中...")
            
            # 30秒后退出
            if frame_count > 3000:
                break
                
    except KeyboardInterrupt:
        print("\n用户中断")
    finally:
        await audio.stop()
    
    print("-" * 50)
    print(f"总计: {frame_count} 帧, {speech_frames} 次语音检测")
    
    if speech_frames == 0:
        print("\n⚠️ 没有检测到语音!")
        print("请检查:")
        print("  1. 麦克风音量是否太低?")
        print("  2. 麦克风是否被其他程序占用?")
    else:
        print("\n✓ VAD检测正常!")

if __name__ == "__main__":
    asyncio.run(main())
