"""Debug test for tool registry."""
import asyncio
from pathlib import Path
from kaolalabot.agent.tools import create_default_tools

async def test():
    tools = create_default_tools(workspace=Path("./workspace"))
    print("=== Registered Tools ===")
    print(f"Total tools: {len(tools)}")
    print(f"Tool names: {tools.tool_names}")
    print()
    print("=== Tool Definitions ===")
    for td in tools.get_definitions():
        print(td)
    print()

asyncio.run(test())
