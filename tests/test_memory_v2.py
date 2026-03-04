"""Test script for Memory System V2."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from kaolalabot.memory.manager_v2 import MemoryManagerV2
from kaolalabot.memory.models import ContentSource, MemoryType, TaskLog


async def test_memory_system():
    print("=" * 50)
    print("Testing Memory System V2")
    print("=" * 50)
    
    workspace = Path("./workspace")
    workspace.mkdir(parents=True, exist_ok=True)
    
    manager = MemoryManagerV2(
        workspace=workspace,
        config={
            "working_max_size": 10,
            "decay_rate": 0.95,
            "archive_threshold": 0.3,
        }
    )
    print("\n1. MemoryManagerV2 initialized successfully")
    
    memory1 = await manager.ingest(
        content="用户喜欢在下午3点提交代码审查请求",
        source=ContentSource.USER_INPUT,
        session_id="test_session_001"
    )
    print(f"2. Ingested fact memory: {memory1.id[:8] if memory1 else 'None'}")
    assert memory1 is not None, "Failed to ingest memory"
    assert memory1.type == MemoryType.SEMANTIC, f"Expected SEMANTIC, got {memory1.type}"
    
    memory2 = await manager.ingest(
        content="hello",  # should be filtered as noise
        source=ContentSource.USER_INPUT,
        session_id="test_session_001"
    )
    print(f"3. Noise test (should be None): {memory2}")
    assert memory2 is None, "Noise should be filtered"
    
    memory3 = await manager.ingest(
        content="如何修复Python中的ImportError?",
        source=ContentSource.USER_INPUT,
        session_id="test_session_001"
    )
    print(f"4. Ingested skill question: {memory3.id[:8] if memory3 else 'None'}")
    assert memory3 is not None
    assert memory3.type == MemoryType.PROCEDURAL, f"Expected PROCEDURAL, got {memory3.type}"
    
    memory4 = await manager.ingest(
        content="当前任务是更新用户配置文件",
        source=ContentSource.USER_INPUT,
        session_id="test_session_001"
    )
    print(f"5. Ingested temp state: {memory4.id[:8] if memory4 else 'None'}")
    assert memory4 is not None
    assert memory4.type == MemoryType.WORKING, f"Expected WORKING, got {memory4.type}"
    
    memory5 = await manager.ingest(
        content="执行了git commit命令",
        source=ContentSource.LOG,
        session_id="test_session_001"
    )
    print(f"6. Ingested event: {memory5.id[:8] if memory5 else 'None'}")
    assert memory5 is not None
    
    print("\n7. Testing retrieval...")
    results = await manager.retrieve(
        query="用户偏好提交代码",
        context={"session_id": "test_session_001"},
        budget=5
    )
    print(f"   Retrieved {len(results)} memories")
    for r in results:
        print(f"   - Score: {r.score:.3f}, Type: {r.memory.type.value}, Content: {r.memory.content_raw[:50]}...")
    
    working = await manager.get_working("test_session_001")
    print(f"\n8. Working memory count: {len(working)}")
    
    semantic = await manager.get_by_type(MemoryType.SEMANTIC)
    print(f"   Semantic memory count: {len(semantic)}")
    
    procedural = await manager.get_by_type(MemoryType.PROCEDURAL)
    print(f"   Procedural memory count: {len(procedural)}")
    
    if results:
        print("\n9. Testing reconsolidation...")
        first_mem_id = results[0].memory.id
        await manager.reconsolidate([first_mem_id], outcome=True)
        print(f"   Reconsolidated memory {first_mem_id[:8]} as success")
    
    print("\n10. Testing procedure extraction...")
    task_log = {
        "task_id": "task_001",
        "task_type": "code_review",
        "start_time": datetime.now().isoformat(),
        "end_time": datetime.now().isoformat(),
        "steps": [
            {"description": "打开代码文件"},
            {"description": "检查代码风格"},
            {"description": "运行测试"},
        ],
        "tool_calls": [
            {"tool": "read_file", "args": {"path": "main.py"}},
            {"tool": "run_command", "args": {"cmd": "pytest"}},
        ],
        "success": True,
        "error": None,
        "recovery_actions": [],
        "observations": ["测试通过", "代码质量良好"],
    }
    
    procedure = await manager.extract_procedure(task_log)
    print(f"    Extracted procedure: {procedure.id[:8] if procedure else 'None'}")
    if procedure and procedure.procedural:
        print(f"    - Action steps: {len(procedure.procedural.action_steps)}")
        print(f"    - Success rate: {procedure.procedural.success_rate}")
    
    stats = manager.get_stats()
    print(f"\n11. Memory stats: {stats}")
    
    print("\n" + "=" * 50)
    print("All tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_memory_system())
