"""Quick test for exec tool."""
import asyncio
from pathlib import Path
from kaolalabot.agent.tools.exec import ExecTool

async def test():
    tool = ExecTool(workspace=Path('./workspace'), timeout=10)
    result = await tool.execute('start notepad')
    print('Result:', result)

asyncio.run(test())
