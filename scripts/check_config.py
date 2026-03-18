import os
from pathlib import Path

# Check possible config paths
paths = [
    Path(__file__).resolve().parent.parent / "config.json",
    Path.home() / ".kaolalabot" / "config.json",
]

for p in paths:
    print(f"{p}: exists={p.exists()}")
    if p.exists():
        print(f"  Content preview:")
        try:
            content = p.read_text(encoding='utf-8')
            print(content[:500])
        except Exception as e:
            print(f"  Error: {e}")
        break
