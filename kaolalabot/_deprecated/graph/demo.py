"""Demo script for Graph Runtime.

This script demonstrates:
1. Normal execution
2. Mid-execution failure and recovery
3. Verification failure and replanning
4. Resuming from checkpoint

Usage:
    python -m kaolalabot.graph.demo
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger

from kaolalabot.graph import (
    GraphRuntime,
    GraphState,
    TaskStatus,
    JsonCheckpointStorage,
    create_default_graph,
)
from kaolalabot.graph.checkpoint import Checkpointer


class MockLLMProvider:
    """Mock LLM provider for demo."""

    def __init__(self, fail_on_step: int = None):
        self.call_count = 0
        self.fail_on_step = fail_on_step

    async def chat(self, messages, **kwargs):
        from dataclasses import dataclass
        
        @dataclass
        class MockResponse:
            content: str = "Task completed successfully."
            has_tool_calls: bool = False
            finish_reason: str = "stop"
            reasoning_content: str = None
            thinking_blocks: list = None

        self.call_count += 1
        
        if self.fail_on_step and self.call_count == self.fail_on_step:
            MockResponse.content = "Error: Simulated failure"
            MockResponse.finish_reason = "error"

        user_msg = messages[-1]["content"] if messages else ""
        
        if "subtask" in user_msg.lower() or "plan" in user_msg.lower():
            MockResponse.content = '''[
                {"id": "task1", "objective": "Analyze the request", "expected_output": "Analysis result", "dependencies": [], "status": "pending"},
                {"id": "task2", "objective": "Execute the main task", "expected_output": "Execution result", "dependencies": ["task1"], "status": "pending"},
                {"id": "task3", "objective": "Verify the result", "expected_output": "Verification result", "dependencies": ["task2"], "status": "pending"}
            ]'''
        elif "verify" in user_msg.lower() or "check" in user_msg.lower():
            MockResponse.content = "PASS - The result meets expectations"
        elif "summarize" in user_msg.lower():
            MockResponse.content = "Summary: Task completed with some issues resolved."
        
        return MockResponse()


class MockToolRegistry:
    """Mock tool registry for demo."""

    def get_definitions(self):
        return []

    async def execute(self, name, arguments):
        return f"Executed {name} with {arguments}"


async def demo_normal_execution():
    """Demo 1: Normal execution flow."""
    print("\n" + "=" * 60)
    print("DEMO 1: Normal Execution")
    print("=" * 60)

    llm = MockLLMProvider()
    tool_registry = MockToolRegistry()

    nodes = create_default_graph(llm_provider=llm, tool_registry=tool_registry)

    checkpointer = Checkpointer(storage_dir="./workspace/graph_checkpoints/demo1")

    runtime = GraphRuntime(
        nodes=nodes,
        checkpointer=checkpointer,
        max_steps=20,
    )

    state = await runtime.run(
        goal="Read the file README.md and summarize its content",
        task_id="demo1_normal",
    )

    print(f"\nFinal Status: {state.status.value}")
    print(f"Total Steps: {state.current_step}")
    print(f"Plan Length: {len(state.plan)}")
    print(f"Completed Tasks: {len([s for s in state.plan if s.status.value == 'done'])}")
    print(f"Errors: {len(state.errors)}")

    return state


async def demo_with_failure():
    """Demo 2: Execution with simulated failure and recovery."""
    print("\n" + "=" * 60)
    print("DEMO 2: Failure and Recovery")
    print("=" * 60)

    llm = MockLLMProvider(fail_on_step=3)
    tool_registry = MockToolRegistry()

    nodes = create_default_graph(llm_provider=llm, tool_registry=tool_registry)

    checkpointer = Checkpointer(storage_dir="./workspace/graph_checkpoints/demo2")

    runtime = GraphRuntime(
        nodes=nodes,
        checkpointer=checkpointer,
        max_steps=20,
    )

    state = await runtime.run(
        goal="Process the user request with error handling",
        task_id="demo2_failure",
    )

    print(f"\nFinal Status: {state.status.value}")
    print(f"Total Steps: {state.current_step}")
    print(f"Errors: {len(state.errors)}")
    if state.errors:
        print(f"Last Error: {state.errors[-1]}")

    return state


async def demo_resume_from_checkpoint():
    """Demo 3: Resume from checkpoint."""
    print("\n" + "=" * 60)
    print("DEMO 3: Resume from Checkpoint")
    print("=" * 60)

    llm = MockLLMProvider()
    tool_registry = MockToolRegistry()

    nodes = create_default_graph(llm_provider=llm, tool_registry=tool_registry)

    checkpointer = Checkpointer(storage_dir="./workspace/graph_checkpoints/demo1")

    info = checkpointer.get_latest_checkpoint_info("demo1_normal")
    if info:
        print(f"Found checkpoint: {info}")

        state = checkpointer.resume_from_latest("demo1_normal")
        if state:
            print(f"Resumed from step {state.current_step}")

            runtime = GraphRuntime(
                nodes=nodes,
                checkpointer=checkpointer,
                max_steps=20,
            )

            state = await runtime.run(
                goal="Continue from checkpoint",
                initial_state=state,
            )

            print(f"\nResumed Status: {state.status.value}")
            print(f"Total Steps: {state.current_step}")
        else:
            print("Failed to load state from checkpoint")
    else:
        print("No checkpoint found, run demo1 first")

    return None


async def demo_state_inspection():
    """Demo 4: Inspect state at checkpoints."""
    print("\n" + "=" * 60)
    print("DEMO 4: State Inspection")
    print("=" * 60)

    checkpointer = Checkpointer(storage_dir="./workspace/graph_checkpoints/demo1")

    checkpoints = checkpointer.inspect_state("demo1_normal")
    print(f"Found {len(checkpoints)} checkpoints")

    for cp in checkpoints[-3:]:
        print(f"\n  Checkpoint: {cp.checkpoint_id[:8]}...")
        print(f"  Node: {cp.node_name}")
        print(f"  Step: {cp.full_state.current_step}")
        print(f"  Status: {cp.full_state.status.value}")


async def main():
    """Run all demos."""
    logger.disable("kaolalabot")
    
    print("\n" + "#" * 60)
    print("# Graph Runtime Demo")
    print("#" * 60)

    try:
        await demo_normal_execution()
    except Exception as e:
        print(f"Demo 1 error: {e}")

    try:
        await demo_with_failure()
    except Exception as e:
        print(f"Demo 2 error: {e}")

    try:
        await demo_state_inspection()
    except Exception as e:
        print(f"Demo 4 error: {e}")

    try:
        await demo_resume_from_checkpoint()
    except Exception as e:
        print(f"Demo 3 error: {e}")

    print("\n" + "#" * 60)
    print("# All Demos Completed")
    print("#" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
