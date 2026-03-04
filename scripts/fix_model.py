"""重新下载并修复ASR模型"""
import os
import shutil

# 设置镜像
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

print("=== 修复 ASR 模型 ===")
print("正在删除损坏的模型缓存...")

cache_path = os.path.expanduser(r"~\.cache\huggingface\hub\models--Systran--faster-whisper-tiny")

if os.path.exists(cache_path):
    print(f"删除: {cache_path}")
    shutil.rmtree(cache_path)
    print("已删除")

print("\n正在重新下载模型 (tiny, 约39MB)...")
print("使用镜像: https://hf-mirror.com")
print("这可能需要1-3分钟...")

try:
    from faster_whisper import WhisperModel
    
    # 下载并加载模型
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    
    print("\n✓ 模型下载并加载成功!")
    print(f"模型路径: {model}")
    
except Exception as e:
    print(f"\n✗ 下载失败: {e}")
    print("\n请手动执行以下命令:")
    print("  set HF_ENDPOINT=https://hf-mirror.com")
    print("  python -c \"from faster_whisper import WhisperModel; WhisperModel('tiny')\"")
