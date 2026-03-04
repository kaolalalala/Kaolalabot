import subprocess
import sys
import time

process = subprocess.Popen(
    [sys.executable, "run_voice.py"],
    cwd="d:/ai/kaolalabot",
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

# Wait 15 seconds for user to speak
time.sleep(15)

# Terminate and get output
process.terminate()
try:
    stdout, _ = process.communicate(timeout=3)
except:
    stdout = process.stdout.read() if process.stdout else ""

print("OUTPUT:")
print(stdout[:5000])
