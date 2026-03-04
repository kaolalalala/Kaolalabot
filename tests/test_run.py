import subprocess
import sys
import time

process = subprocess.Popen(
    [sys.executable, "run_voice.py"],
    cwd="d:/ai/kaolalabot",
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Wait 8 seconds for startup
time.sleep(8)

# Terminate and get output
process.terminate()
try:
    stdout, stderr = process.communicate(timeout=3)
except:
    stdout, stderr = process.communicate()

print("STDOUT:")
print(stdout[:3000])
print("\nSTDERR:")
print(stderr[:3000])
