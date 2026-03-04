import subprocess
import sys

result = subprocess.run(
    [sys.executable, "run_voice.py"],
    cwd="d:/ai/kaolalabot",
    capture_output=True,
    text=True,
    timeout=15
)

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print("\nReturn code:", result.returncode)
