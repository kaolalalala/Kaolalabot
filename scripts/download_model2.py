"""使用huggingface-cli下载模型"""
import subprocess
import os

# 设置环境变量
env = os.environ.copy()
env["HF_ENDPOINT"] = "https://hf-mirror.com"

print("=== 使用 huggingface-cli 下载模型 ===")
print("命令: huggingface-cli download Systran/faster-whisper-tiny")
print()

try:
    result = subprocess.run(
        ["huggingface-cli", "download", "Systran/faster-whisper-tiny"],
        env=env,
        capture_output=True,
        text=True,
        timeout=300
    )
    
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    print("Return code:", result.returncode)
    
except FileNotFoundError:
    print("huggingface-cli 未安装")
    print("尝试使用: pip install huggingface-hub")
except Exception as e:
    print(f"Error: {e}")
