import subprocess
import sys
import time
import os

# Set environment to capture all output
env = os.environ.copy()
env["PYTHONUNBUFFERED"] = "1"

process = subprocess.Popen(
    [sys.executable, "run_voice.py"],
    cwd="d:/ai/kaolalabot",
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
    env=env
)

# Wait 12 seconds for user to speak
time.sleep(12)

# Terminate and get output
process.terminate()
try:
    stdout, _ = process.communicate(timeout=3)
except:
    try:
        stdout = process.stdout.read() if process.stdout else ""
    except:
        stdout = ""

print("OUTPUT:")
print(stdout[:8000])
