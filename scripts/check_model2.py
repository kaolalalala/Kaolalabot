import os
from pathlib import Path

path = Path.home() / ".cache" / "huggingface" / "hub" / "models--Systran--faster-whisper-tiny"

print("模型目录:", path)
print("是否存在:", path.exists())
print()

if path.exists():
    for item in path.iterdir():
        if item.is_file():
            size = item.stat().st_size
            print(f"文件: {item.name} - {size/1024/1024:.2f} MB")
        elif item.is_dir():
            print(f"目录: {item.name}/")
            for subitem in item.iterdir():
                if subitem.is_file():
                    size = subitem.stat().st_size
                    print(f"  - {subitem.name} - {size/1024/1024:.2f} MB")
