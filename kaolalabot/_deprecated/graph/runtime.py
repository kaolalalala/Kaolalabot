"""Graph Runtime - Core Runtime Executor."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from kaolalabot.graph.state import ErrorType, GraphState, TaskStatus
from kaolalabot.graph.nodes.base import BaseNode, NodeResult
from kaolalabot.graph.nodes import create_default_graph
from kaolalabot.graph.edges import SimpleRouter, RouteDecision
from kaolalabot.graph.checkpoint import Checkpointer, JsonCheckpointStorage


class RuntimeStatus(str, Enum):
    """Runtime execution status."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionEvent(str, Enum):
    """Events during execution."""
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    CHECKPOINT_SAVED = "checkpoint_saved"
    STATUS_CHANGED = "status_changed"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    ERROR = "error"


class GraphRuntime:
    """
    Core graph execution runtime.
    
    Responsibilities:
    - Execute nodes in order based on router
    - Manage checkpoints
    - Handle errors and recovery
    - Support pause/resume/cancel
    - Emit events for monitoring
    """

    def __init__(
        self,
        nodes: dict[str, BaseNode] | None = None,
        router: SimpleRouter | None = None,
        checkpointer: Checkpointer | None = None,
        max_steps: int = 100,
        step_timeout: int = 300,
        enable_checkpoint: bool = True,
    ):
        self.nodes = nodes or create_default_graph()
        self.router = router or SimpleRouter()
        self.checkpointer = checkpointer or Checkpointer()
        self.max_steps = max_steps
        self.step_timeout = step_timeout
        self.enable_checkpoint = enable_checkpoint
        
        self._status = RuntimeStatus.IDLE
        self._current_task_id: str | None = None
        self._current_node: str | None = None
        self._current_checkpoint_id: str | None = None
        self._event_handlers: dict[ExecutionEvent, list[Callable]] = {
            event: [] for event in ExecutionEvent
        }
        self._execution_logs: list[dict] = []
        self._cancelled = False
        self._paused = False

    @property
    def status(self) -> RuntimeStatus:
        """Get current runtime status."""
        return self._status

    @property
    def current_task_id(self) -> str | None:
        """Get current task ID."""
        return self._current_task_id

    def on(self, event: ExecutionEvent, handler: Callable) -> None:
        """Register an event handler."""
        self._event_handlers[event].append(handler)

    def _emit(self, event: ExecutionEvent, data: dict) -> None:
        """Emit an event to all handlers."""
        for handler in self._event_handlers[event]:
            try:
                handler(data)
            except Exception as e:
                logger.warning(f"Event handler error: {e}")
        
        self._execution_logs.append({
            "event": event.value,
            "timestamp": datetime.now().isoformat(),
            **data,
        })

    async def run(
        self,
        goal: str,
        task_id: str | None = None,
        initial_state: GraphState | None = None,
        deep_thinking: bool = False,
    ) -> GraphState:
        """
        Run the graph with the given goal.
        
        Args:
            goal: The user goal to accomplish
            task_id: Optional task ID for resuming
            initial_state: Optional initial state for resuming
            deep_thinking: Whether to enable deep thinking mode
            
        Returns:
            Final GraphState after execution
        """
        self._status = RuntimeStatus.RUNNING
        self._cancelled = False
        self._paused = False
        
        if initial_state:
            state = initial_state
            self._current_task_id = state.task_id
            if state.status == TaskStatus.PAUSED:
                self._status = RuntimeStatus.PAUSED
            elif state.status == TaskStatus.FINISHED:
                logger.info(f"[Runtime] Task {state.task_id} already finished, returning state")
                self._status = RuntimeStatus.COMPLETED
                return state
        else:
            task_id = task_id or str(uuid.uuid4())
            self._current_task_id = task_id
            state = GraphState(
                task_id=task_id,
                goal=goal,
                deep_thinking_enabled=deep_thinking,
            )
        
        logger.info(f"[Runtime] Starting task {state.task_id} with goal: {goal[:50]}...")
        
        self._emit(ExecutionEvent.STATUS_CHANGED, {"status": self._status.value})

        try:
            state = await self._execute_graph(state)
        except asyncio.CancelledError:
            logger.info(f"[Runtime] Task {state.task_id} cancelled")
            state.status = TaskStatus.CANCELLED
            self._status = RuntimeStatus.CANCELLED
        except Exception as e:
            logger.exception(f"[Runtime] Task {state.task_id} failed: {e}")
            state.status = TaskStatus.FAILED
            state.add_error("runtime", ErrorType.UNKNOWN, str(e), recoverable=False)
            self._status = RuntimeStatus.FAILED
        finally:
            self._emit(ExecutionEvent.STATUS_CHANGED, {"status": self._status.value})

        return state

    async def _execute_graph(self, state: GraphState) -> GraphState:
        """Execute the graph loop."""
        current_node = "planner"
        
        while state.current_step < self.max_steps:
            if self._cancelled:
                state.status = TaskStatus.CANCELLED
                break
            
            if self._paused or state.human_review_required:
                state.status = TaskStatus.PAUSED
                self._status = RuntimeStatus.PAUSED
                self._emit(ExecutionEvent.HUMAN_REVIEW_REQUIRED, {
                    "task_id": state.task_id,
                    "current_node": current_node,
                    "state_summary": self._get_state_summary(state),
                })
                break

            if current_node not in self.nodes:
                logger.warning(f"[Runtime] Unknown node: {current_node}, ending execution")
                break

            node = self.nodes[current_node]
            start_time = datetime.now()
            
            self._emit(ExecutionEvent.NODE_STARTED, {
                "task_id": state.task_id,
                "node": current_node,
                "step": state.current_step,
            })

            try:
                result = await asyncio.wait_for(
                    node.execute(state),
                    timeout=self.step_timeout,
                )
            except asyncio.TimeoutError:
                logger.error(f"[Runtime] Node {current_node} timed out")
                state.add_error(current_node, ErrorType.TRANSIENT, f"Node timed out after {self.step_timeout}s")
                result = NodeResult(
                    state=state,
                    success=False,
                    error=f"Node timed out after {self.step_timeout}s",
                    error_type=ErrorType.TRANSIENT,
                )
            except Exception as e:
                logger.exception(f"[Runtime] Node {current_node} failed: {e}")
                state.add_error(current_node, ErrorType.UNKNOWN, str(e))
                result = NodeResult(
                    state=state,
                    success=False,
                    error=str(e),
                    error_type=ErrorType.UNKNOWN,
                )

            end_time = datetime.now()
            elapsed_ms = int((end_time - start_time).total_seconds() * 1000)

            state.add_node_history(current_node, start_time, end_time, result.success, result.error)

            if result.human_review:
                state.human_review_required = True
                state.status = TaskStatus.PAUSED
                self._status = RuntimeStatus.PAUSED
                self._emit(ExecutionEvent.HUMAN_REVIEW_REQUIRED, {
                    "task_id": state.task_id,
                    "current_node": current_node,
                    "reason": result.error,
                })
                break

            if not result.success:
                self._emit(ExecutionEvent.NODE_FAILED, {
                    "task_id": state.task_id,
                    "node": current_node,
                    "error": result.error,
                    "error_type": result.error_type.value if result.error_type else "unknown",
                })

            if self.enable_checkpoint:
                checkpoint = self.checkpointer.save_checkpoint(state, current_node, self._current_checkpoint_id)
                self._current_checkpoint_id = checkpoint.checkpoint_id
                self._emit(ExecutionEvent.CHECKPOINT_SAVED, {
                    "task_id": state.task_id,
                    "checkpoint_id": checkpoint.checkpoint_id,
                    "node": current_node,
                })

            if result.success and result.next_node:
                current_node = result.next_node
            elif not result.success:
                current_node = "diagnoser"
            else:
                break

            self._emit(ExecutionEvent.NODE_COMPLETED, {
                "task_id": state.task_id,
                "node": current_node,
                "elapsed_ms": elapsed_ms,
                "success": result.success,
            })

            await asyncio.sleep(0)

        if state.current_step >= self.max_steps:
            logger.warning(f"[Runtime] Max steps ({self.max_steps}) reached")
            state.status = TaskStatus.FAILED
            state.add_error("runtime", ErrorType.LOOP, f"Max steps ({self.max_steps}) reached")
            self._status = RuntimeStatus.FAILED
        elif state.status not in [TaskStatus.PAUSED, TaskStatus.CANCELLED, TaskStatus.FAILED]:
            state.status = TaskStatus.FINISHED
            self._status = RuntimeStatus.COMPLETED

        return state

    def _get_state_summary(self, state: GraphState) -> dict:
        """Get a summary of current state for human review."""
        return {
            "goal": state.goal,
            "current_step": state.current_step,
            "current_subtask": state.get_current_subtask().objective if state.get_current_subtask() else None,
            "completed_subtasks": len([s for s in state.plan if s.status.value == "done"]),
            "pending_subtasks": len(state.get_pending_subtasks()),
            "failed_subtasks": len(state.get_failed_subtasks()),
            "recent_errors": state.errors[-3:] if state.errors else [],
        }

    def pause(self) -> None:
        """Pause execution."""
        self._paused = True
        logger.info("[Runtime] Execution paused")

    def resume(self) -> None:
        """Resume execution."""
        self._paused = False
        logger.info("[Runtime] Execution resumed")

    def cancel(self) -> None:
        """Cancel execution."""
        self._cancelled = True
        logger.info("[Runtime] Execution cancelled")

    async def resume_task(
        self,
        task_id: str,
        checkpoint_id: str | None = None,
    ) -> GraphState:
        """
        Resume a task from checkpoint.
        
        Args:
            task_id: The task ID to resume
            checkpoint_id: Optional specific checkpoint ID, otherwise uses latest
            
        Returns:
            Resumed GraphState
        """
        if checkpoint_id:
            state = self.checkpointer.resume_from_checkpoint(task_id, checkpoint_id)
        else:
            state = self.checkpointer.resume_from_latest(task_id)
        
        if not state:
            raise ValueError(f"No checkpoint found for task {task_id}")
        
        logger.info(f"[Runtime] Resuming task {task_id} from step {state.current_step}")
        
        return await self.run(
            goal=state.goal,
            initial_state=state,
        )

    def get_execution_logs(self) -> list[dict]:
        """Get execution logs."""
        return self._execution_logs

    def get_task_info(self, task_id: str) -> dict | None:
        """Get task info from latest checkpoint."""
        return self.checkpointer.get_latest_checkpoint_info(task_id)

    def list_tasks(self) -> list[dict]:
        """List all tasks."""
        return []


__all__ = [
    "GraphRuntime",
    "RuntimeStatus",
    "ExecutionEvent",
]
