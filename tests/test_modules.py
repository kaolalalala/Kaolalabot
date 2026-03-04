"""Test script for memory and cot modules."""

import asyncio
import sys
sys.path.insert(0, 'D:/ai/kaolalabot')

async def test_memory():
    print("Testing Memory Module...")
    
    from pathlib import Path
    from kaolalabot.memory.manager import MemoryManager
    
    workspace = Path("D:/ai/kaolalabot/workspace")
    manager = MemoryManager(workspace)
    
    await manager.add("用户说: 你好", "working", session_id="test")
    print("✓ Added working memory")
    
    memories = await manager.get_working()
    print(f"✓ Working memories: {len(memories)}")
    
    await manager.add("这是重要信息，请记住", "episodic", session_id="test")
    print("✓ Added episodic memory")
    
    results = await manager.recall("重要", "test")
    print(f"✓ Recall results: {len(results)}")
    
    print("\nMemory module OK!")
    return True


async def test_cot():
    print("\nTesting CoT Engine...")
    
    from kaolalabot.agent.cot.engine import CoTEngine, ThinkStep, ThinkPhase
    
    print("✓ CoT imports OK")
    
    step = ThinkStep(
        phase=ThinkPhase.OBSERVE,
        content="Test content",
        reasoning="Test reasoning"
    )
    print(f"✓ Created ThinkStep: {step.id}")
    
    return True


async def main():
    try:
        await test_memory()
        await test_cot()
        print("\n✅ All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
