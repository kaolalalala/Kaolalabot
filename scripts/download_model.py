#!/usr/bin/env python
"""预下载ASR模型脚本"""

import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import sys

print("=== 预下载 Whisper 模型 ===")
print("模型: tiny (约39MB)")
print("来源: HuggingFace (使用国内镜像)")
print()

try:
    from faster_whisper import WhisperModel
    
    print("开始下载模型...")
    print("(可能需要1-3分钟，取决于网络)")
    
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    
    print()
    print("✓ 模型下载并加载成功!")
    print()
    print("模型信息:", model)
    
except KeyboardInterrupt:
    print("\n下载已取消")
except Exception as e:
    print(f"\n下载失败: {e}")
    print("\n解决方法:")
    print("1. 检查网络连接")
    print("2. 手动下载模型文件")
