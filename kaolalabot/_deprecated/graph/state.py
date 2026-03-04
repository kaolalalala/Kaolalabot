"""Graph Runtime - State definitions."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    FAILED = "failed"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class ErrorType(str, Enum):
    TRANSIENT = "transient"
    VALIDATION = "validation"
    ENVIRONMENT = "environment"
    REASONING = "reasoning"
    RESOURCE = "resource"
    LOOP = "loop"
    UNKNOWN = "unknown"


class SubTaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class SubTask:
    """A single subtask in the plan."""

    def __init__(
        self,
        id: str,
        objective: str,
        expected_output: str | None = None,
        dependencies: list[str] | None = None,
    ):
        self.id = id
        self.objective = objective
        self.expected_output = expected_output
        self.dependencies = dependencies or []
        self.status = SubTaskStatus.PENDING
        self.result: Any = None
        self.error: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "objective": self.objective,
            "expected_output": self.expected_output,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "result": self.result if isinstance(self.result, (str, int, float, bool, type(None))) else str(self.result),
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SubTask:
        task = cls(
            id=data["id"],
            objective=data["objective"],
            expected_output=data.get("expected_output"),
            dependencies=data.get("dependencies", []),
        )
        task.status = SubTaskStatus(data.get("status", "pending"))
        task.result = data.get("result")
        task.error = data.get("error")
        return task


class GraphState:
    """
    Shared state for the graph execution.
    
    All nodes read and write only this state object.
    State is JSON-serializable for checkpoint persistence.
    """

    def __init__(
        self,
        task_id: str | None = None,
        goal: str = "",
        plan: list[SubTask] | None = None,
        current_step: int = 0,
        node_history: list[dict] | None = None,
        tool_history: list[dict] | None = None,
        artifacts: dict | None = None,
        errors: list[dict] | None = None,
        retry_count: int = 0,
        status: TaskStatus = TaskStatus.RUNNING,
        last_progress_at: datetime | None = None,
        human_review_required: bool = False,
        metadata: dict | None = None,
        deep_thinking_enabled: bool = False,
        current_subtask_id: str | None = None,
    ):
        self.task_id = task_id or str(uuid.uuid4())
        self.goal = goal
        self.plan = plan or []
        self.current_step = current_step
        self.node_history = node_history or []
        self.tool_history = tool_history or []
        self.artifacts = artifacts or {}
        self.errors = errors or []
        self.retry_count = retry_count
        self.status = status
        self.last_progress_at = last_progress_at or datetime.now()
        self.human_review_required = human_review_required
        self.metadata = metadata or {}
        self.deep_thinking_enabled = deep_thinking_enabled
        self.current_subtask_id = current_subtask_id

    def get_current_subtask(self) -> SubTask | None:
        """Get the current subtask based on current_subtask_id."""
        if not self.current_subtask_id:
            for subtask in self.plan:
                if subtask.status == SubTaskStatus.RUNNING:
                    return subtask
            return None
        for subtask in self.plan:
            if subtask.id == self.current_subtask_id:
                return subtask
        return None

    def get_pending_subtasks(self) -> list[SubTask]:
        """Get all pending subtasks."""
        return [s for s in self.plan if s.status == SubTaskStatus.PENDING]

    def get_failed_subtasks(self) -> list[SubTask]:
        """Get all failed subtasks."""
        return [s for s in self.plan if s.status == SubTaskStatus.FAILED]

    def mark_subtask_done(self, subtask_id: str, result: Any = None) -> None:
        """Mark a subtask as done."""
        for subtask in self.plan:
            if subtask.id == subtask_id:
                subtask.status = SubTaskStatus.DONE
                subtask.result = result
                break
        self.last_progress_at = datetime.now()

    def mark_subtask_failed(self, subtask_id: str, error: str | None = None) -> None:
        """Mark a subtask as failed."""
        for subtask in self.plan:
            if subtask.id == subtask_id:
                subtask.status = SubTaskStatus.FAILED
                subtask.error = error
                break

    def add_error(self, node_name: str, error_type: ErrorType, message: str, recoverable: bool = True) -> None:
        """Add an error record."""
        self.errors.append({
            "node": node_name,
            "type": error_type.value,
            "message": message,
            "recoverable": recoverable,
            "timestamp": datetime.now().isoformat(),
        })
        self.last_progress_at = datetime.now()

    def add_node_history(self, node_name: str, start_time: datetime, end_time: datetime, success: bool, error: str | None = None) -> None:
        """Add a node execution record to history."""
        self.node_history.append({
            "node": node_name,
            "step": self.current_step,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "elapsed_ms": int((end_time - start_time).total_seconds() * 1000),
            "success": success,
            "error": error,
        })
        self.current_step += 1
        self.last_progress_at = datetime.now()

    def to_dict(self) -> dict:
        """Serialize state to dictionary."""
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "plan": [s.to_dict() for s in self.plan],
            "current_step": self.current_step,
            "node_history": self.node_history,
            "tool_history": self.tool_history,
            "artifacts": self.artifacts,
            "errors": self.errors,
            "retry_count": self.retry_count,
            "status": self.status.value,
            "last_progress_at": self.last_progress_at.isoformat() if self.last_progress_at else None,
            "human_review_required": self.human_review_required,
            "metadata": self.metadata,
            "deep_thinking_enabled": self.deep_thinking_enabled,
            "current_subtask_id": self.current_subtask_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> GraphState:
        """Deserialize state from dictionary."""
        state = cls(
            task_id=data.get("task_id"),
            goal=data.get("goal", ""),
            current_step=data.get("current_step", 0),
            node_history=data.get("node_history", []),
            tool_history=data.get("tool_history", []),
            artifacts=data.get("artifacts", {}),
            errors=data.get("errors", []),
            retry_count=data.get("retry_count", 0),
            status=TaskStatus(data.get("status", "running")),
            human_review_required=data.get("human_review_required", False),
            metadata=data.get("metadata", {}),
            deep_thinking_enabled=data.get("deep_thinking_enabled", False),
            current_subtask_id=data.get("current_subtask_id"),
        )
        
        if "plan" in data and data["plan"]:
            state.plan = [SubTask.from_dict(p) for p in data["plan"]]
        
        if "last_progress_at" in data and data["last_progress_at"]:
            state.last_progress_at = datetime.fromisoformat(data["last_progress_at"])
        
        return state

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> GraphState:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def __repr__(self) -> str:
        return f"GraphState(task_id={self.task_id[:8]}..., status={self.status.value}, step={self.current_step}, plan_len={len(self.plan)})"
