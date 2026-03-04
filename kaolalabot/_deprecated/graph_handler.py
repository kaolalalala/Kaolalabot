"""Graph Handler - Integration between Gateway and Graph Runtime."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from kaolalabot.graph import GraphRuntime, GraphState, TaskStatus
from kaolalabot.graph.checkpoint import JsonCheckpointStorage


class TaskDifficulty(str):
    """Task difficulty classification."""
    SIMPLE = "simple"
    COMPLEX = "complex"


class GraphHandler:
    """
    Handler for managing Graph Runtime integration with Gateway.
    
    Responsibilities:
    - Route tasks to appropriate execution path (loop vs graph)
    - Determine if deep thinking should be enabled
    - Manage task execution and checkpointing
    - Provide status and control APIs
    """

    def __init__(
        self,
        workspace: Path | str | None = None,
        checkpointer: JsonCheckpointStorage | None = None,
        llm_provider=None,
        agent_loop=None,
        tool_registry=None,
    ):
        self.workspace = Path(workspace) if workspace else Path("./workspace")
        self.checkpointer = checkpointer or JsonCheckpointStorage(self.workspace / "graph_checkpoints")
        
        self._llm_provider = llm_provider
        self._agent_loop = agent_loop
        self._tool_registry = tool_registry
        
        self._runtimes: dict[str, GraphRuntime] = {}
        self._deep_thinking_enabled = False
        self._auto_detect_complex = True
        
        self._progress_callbacks: list[Callable] = []

    def set_deep_thinking_mode(self, enabled: bool) -> None:
        """Enable or disable deep thinking mode globally."""
        self._deep_thinking_enabled = enabled
        logger.info(f"[GraphHandler] Deep thinking mode: {enabled}")

    def get_deep_thinking_mode(self) -> bool:
        """Get current deep thinking mode setting."""
        return self._deep_thinking_enabled

    def enable_auto_detect_complex(self, enabled: bool) -> None:
        """Enable or disable auto-detection of complex tasks."""
        self._auto_detect_complex = enabled
        logger.info(f"[GraphHandler] Auto-detect complex tasks: {enabled}")

    def on_progress(self, callback: Callable[[dict], None]) -> None:
        """Register a progress callback."""
        self._progress_callbacks.append(callback)

    def _emit_progress(self, data: dict) -> None:
        """Emit progress to all callbacks."""
        for cb in self._progress_callbacks:
            try:
                cb(data)
            except Exception as e:
                logger.warning(f"[GraphHandler] Progress callback error: {e}")

    async def _determine_difficulty(self, message: str) -> TaskDifficulty:
        """Use LLM to determine task difficulty."""
        if not self._llm_provider:
            return TaskDifficulty.SIMPLE
        
        try:
            prompt = f"""Analyze this user request and determine if it requires complex planning:

User Request: {message}

Consider:
- Multi-step tasks requiring planning
- Tasks with multiple dependencies
- Tasks needing error recovery
- Tasks requiring verification

Respond with ONLY "simple" or "complex":
- "simple" for straightforward requests that can be completed in one step
- "complex" for tasks requiring planning, multiple steps, or error handling
"""
            response = await self._llm_provider.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=50,
            )
            
            content = (response.content or "").strip().lower()
            if "complex" in content:
                return TaskDifficulty.COMPLEX
            return TaskDifficulty.SIMPLE
            
        except Exception as e:
            logger.warning(f"[GraphHandler] Difficulty detection failed: {e}")
            return TaskDifficulty.SIMPLE

    def should_use_graph(self, message: str) -> bool:
        """Determine if the graph execution should be used."""
        if self._deep_thinking_enabled:
            return True
        
        if not self._auto_detect_complex:
            return False
        
        return False

    async def execute(
        self,
        message: str,
        session_key: str | None = None,
        use_graph: bool | None = None,
        deep_thinking: bool | None = None,
    ) -> tuple[str, GraphState | None]:
        """
        Execute a message.
        
        Args:
            message: The user message
            session_key: Optional session key
            use_graph: Force graph mode, None for auto-detect
            deep_thinking: Force deep thinking, None for auto-detect
            
        Returns:
            Tuple of (response_text, state)
        """
        if use_graph is None:
            use_graph = self.should_use_graph(message)
        
        if deep_thinking is None:
            deep_thinking = self._deep_thinking_enabled
        
        if use_graph:
            return await self._execute_graph(message, session_key, deep_thinking)
        else:
            return await self._execute_loop(message, session_key)

    async def _execute_graph(
        self,
        message: str,
        session_key: str | None = None,
        deep_thinking: bool = False,
    ) -> tuple[str, GraphState]:
        """Execute using Graph Runtime."""
        logger.info(f"[GraphHandler] Using graph execution (deep_thinking={deep_thinking})")
        
        from kaolalabot.graph.nodes import create_default_graph
        
        nodes = create_default_graph(
            llm_provider=self._llm_provider,
            agent_loop=self._agent_loop,
            tool_registry=self._tool_registry,
        )
        
        runtime = GraphRuntime(
            nodes=nodes,
            checkpointer=self.checkpointer,
            max_steps=50,
        )
        
        task_id = session_key or f"task_{id(message)}"
        self._runtimes[task_id] = runtime
        
        runtime.on("node_started", lambda d: self._emit_progress(d))
        runtime.on("node_completed", lambda d: self._emit_progress(d))
        runtime.on("human_review_required", lambda d: self._emit_progress(d))
        
        state = await runtime.run(
            goal=message,
            task_id=task_id,
            deep_thinking=deep_thinking,
        )
        
        response = state.artifacts.get("final_summary", "Task completed")
        
        return response, state

    async def _execute_loop(
        self,
        message: str,
        session_key: str | None = None,
    ) -> tuple[str, None]:
        """Execute using standard agent loop."""
        logger.info("[GraphHandler] Using standard loop execution")
        
        if not self._agent_loop:
            return "Agent loop not configured", None
        
        result = await self._agent_loop.process_direct(
            content=message,
            session_key=session_key or "default",
        )
        
        return result, None

    async def resume_task(
        self,
        task_id: str,
        checkpoint_id: str | None = None,
    ) -> tuple[str, GraphState]:
        """Resume a task from checkpoint."""
        from kaolalabot.graph.nodes import create_default_graph
        
        nodes = create_default_graph(
            llm_provider=self._llm_provider,
            agent_loop=self._agent_loop,
            tool_registry=self._tool_registry,
        )
        
        runtime = GraphRuntime(
            nodes=nodes,
            checkpointer=self.checkpointer,
            max_steps=50,
        )
        
        state = await runtime.resume_task(task_id, checkpoint_id)
        
        response = state.artifacts.get("final_summary", "Task resumed")
        
        return response, state

    def get_task_status(self, task_id: str) -> dict | None:
        """Get status of a task."""
        info = self.checkpointer.get_latest_checkpoint_info(task_id)
        if info:
            return {
                "task_id": task_id,
                "checkpoint_id": info.get("checkpoint_id"),
                "current_step": info.get("current_step"),
                "status": info.get("status"),
                "timestamp": info.get("timestamp"),
            }
        
        if task_id in self._runtimes:
            runtime = self._runtimes[task_id]
            return {
                "task_id": task_id,
                "status": runtime.status.value,
                "current_node": runtime._current_node,
            }
        
        return None

    def list_tasks(self) -> list[dict]:
        """List all tasks."""
        import os
        tasks = []
        
        checkpoint_dir = self.workspace / "graph_checkpoints"
        if checkpoint_dir.exists():
            for task_id in os.listdir(checkpoint_dir):
                task_path = checkpoint_dir / task_id
                if task_path.is_dir():
                    info = self.get_task_status(task_id)
                    if info:
                        tasks.append(info)
        
        return tasks

    def pause_task(self, task_id: str) -> bool:
        """Pause a running task."""
        if task_id in self._runtimes:
            self._runtimes[task_id].pause()
            return True
        return False

    def resume_task_sync(self, task_id: str) -> bool:
        """Resume a paused task."""
        if task_id in self._runtimes:
            self._runtimes[task_id].resume()
            return True
        return False

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        if task_id in self._runtimes:
            self._runtimes[task_id].cancel()
            return True
        return False


_graph_handler: GraphHandler | None = None


def get_graph_handler() -> GraphHandler:
    """Get the global graph handler."""
    global _graph_handler
    if _graph_handler is None:
        _graph_handler = GraphHandler()
    return _graph_handler


def set_graph_handler(handler: GraphHandler) -> None:
    """Set the global graph handler."""
    global _graph_handler
    _graph_handler = handler


__all__ = [
    "GraphHandler",
    "TaskDifficulty",
    "get_graph_handler",
    "set_graph_handler",
]
