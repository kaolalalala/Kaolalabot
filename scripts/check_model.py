import os
from pathlib import Path

cache_path = Path.home() / ".cache" / "huggingface" / "hub" / "models--Systran--faster-whisper-tiny"

print("模型文件夹:", cache_path)
print()

if cache_path.exists():
    for item in cache_path.rglob("*"):
        if item.is_file():
            size = item.stat().st_size
            print(f"{item.name}: {size/1024/1024:.2f} MB")
else:
    print("模型文件夹不存在")
