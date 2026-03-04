"""Graph Runtime - Checkpoint Storage."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from kaolalabot.graph.state import GraphState, TaskStatus


class Checkpoint:
    """A checkpoint snapshot of graph state."""

    def __init__(
        self,
        task_id: str,
        checkpoint_id: str | None = None,
        node_name: str = "",
        timestamp: datetime | None = None,
        full_state: GraphState | None = None,
        parent_checkpoint_id: str | None = None,
    ):
        self.task_id = task_id
        self.checkpoint_id = checkpoint_id or str(uuid.uuid4())
        self.node_name = node_name
        self.timestamp = timestamp or datetime.now()
        self.full_state = full_state
        self.parent_checkpoint_id = parent_checkpoint_id

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "task_id": self.task_id,
            "checkpoint_id": self.checkpoint_id,
            "node_name": self.node_name,
            "timestamp": self.timestamp.isoformat(),
            "full_state": self.full_state.to_dict() if self.full_state else {},
            "parent_checkpoint_id": self.parent_checkpoint_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        """Deserialize from dictionary."""
        checkpoint = cls(
            task_id=data["task_id"],
            checkpoint_id=data.get("checkpoint_id"),
            node_name=data.get("node_name", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None,
            parent_checkpoint_id=data.get("parent_checkpoint_id"),
        )
        if "full_state" in data:
            checkpoint.full_state = GraphState.from_dict(data["full_state"])
        return checkpoint


class CheckpointStorage(ABC):
    """Abstract checkpoint storage interface."""

    @abstractmethod
    def save(self, checkpoint: Checkpoint) -> None:
        """Save a checkpoint."""
        pass

    @abstractmethod
    def load(self, task_id: str, checkpoint_id: str) -> Checkpoint | None:
        """Load a checkpoint by ID."""
        pass

    @abstractmethod
    def get_latest(self, task_id: str) -> Checkpoint | None:
        """Get the latest checkpoint for a task."""
        pass

    @abstractmethod
    def get_all(self, task_id: str) -> list[Checkpoint]:
        """Get all checkpoints for a task."""
        pass

    @abstractmethod
    def delete(self, task_id: str, checkpoint_id: str) -> None:
        """Delete a checkpoint."""
        pass


class JsonCheckpointStorage(CheckpointStorage):
    """JSON file-based checkpoint storage."""

    def __init__(self, storage_dir: Path | str):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_task_dir(self, task_id: str) -> Path:
        """Get directory for a task."""
        task_dir = self.storage_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    def _get_index_file(self, task_id: str) -> Path:
        """Get index file for a task."""
        return self._get_task_dir(task_id) / "index.json"

    def save(self, checkpoint: Checkpoint) -> None:
        """Save a checkpoint."""
        index_file = self._get_index_file(checkpoint.task_id)
        
        index = []
        if index_file.exists():
            with open(index_file, "r", encoding="utf-8") as f:
                index = json.load(f)

        checkpoint_file = self._get_task_dir(checkpoint.task_id) / f"{checkpoint.checkpoint_id}.json"
        
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)

        entry = {
            "checkpoint_id": checkpoint.checkpoint_id,
            "node_name": checkpoint.node_name,
            "timestamp": checkpoint.timestamp.isoformat(),
            "parent_checkpoint_id": checkpoint.parent_checkpoint_id,
            "file": f"{checkpoint.checkpoint_id}.json",
        }
        
        existing = [i for i in index if i["checkpoint_id"] != checkpoint.checkpoint_id]
        existing.append(entry)
        
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"[Checkpointer] Saved checkpoint {checkpoint.checkpoint_id} for task {checkpoint.task_id}")

    def load(self, task_id: str, checkpoint_id: str) -> Checkpoint | None:
        """Load a checkpoint by ID."""
        checkpoint_file = self._get_task_dir(task_id) / f"{checkpoint_id}.json"
        
        if not checkpoint_file.exists():
            logger.warning(f"[Checkpointer] Checkpoint {checkpoint_id} not found for task {task_id}")
            return None
        
        with open(checkpoint_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return Checkpoint.from_dict(data)

    def get_latest(self, task_id: str) -> Checkpoint | None:
        """Get the latest checkpoint for a task."""
        index_file = self._get_index_file(task_id)
        
        if not index_file.exists():
            return None
        
        with open(index_file, "r", encoding="utf-8") as f:
            index = json.load(f)
        
        if not index:
            return None
        
        latest = max(index, key=lambda x: x["timestamp"])
        return self.load(task_id, latest["checkpoint_id"])

    def get_all(self, task_id: str) -> list[Checkpoint]:
        """Get all checkpoints for a task."""
        index_file = self._get_index_file(task_id)
        
        if not index_file.exists():
            return []
        
        with open(index_file, "r", encoding="utf-8") as f:
            index = json.load(f)
        
        checkpoints = []
        for entry in sorted(index, key=lambda x: x["timestamp"]):
            cp = self.load(task_id, entry["checkpoint_id"])
            if cp:
                checkpoints.append(cp)
        
        return checkpoints

    def delete(self, task_id: str, checkpoint_id: str) -> None:
        """Delete a checkpoint."""
        checkpoint_file = self._get_task_dir(task_id) / f"{checkpoint_id}.json"
        
        if checkpoint_file.exists():
            checkpoint_file.unlink()
        
        index_file = self._get_index_file(task_id)
        if index_file.exists():
            with open(index_file, "r", encoding="utf-8") as f:
                index = json.load(f)
            
            index = [i for i in index if i["checkpoint_id"] != checkpoint_id]
            
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False, indent=2)


class SQLiteCheckpointStorage(CheckpointStorage):
    """SQLite-based checkpoint storage."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                task_id TEXT NOT NULL,
                checkpoint_id TEXT NOT NULL,
                node_name TEXT,
                timestamp TEXT NOT NULL,
                full_state TEXT NOT NULL,
                parent_checkpoint_id TEXT,
                PRIMARY KEY (task_id, checkpoint_id)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_timestamp 
            ON checkpoints (task_id, timestamp DESC)
        """)
        
        conn.commit()
        conn.close()

    def save(self, checkpoint: Checkpoint) -> None:
        """Save a checkpoint."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO checkpoints 
            (task_id, checkpoint_id, node_name, timestamp, full_state, parent_checkpoint_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            checkpoint.task_id,
            checkpoint.checkpoint_id,
            checkpoint.node_name,
            checkpoint.timestamp.isoformat(),
            checkpoint.full_state.to_json() if checkpoint.full_state else "{}",
            checkpoint.parent_checkpoint_id,
        ))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"[Checkpointer] Saved checkpoint {checkpoint.checkpoint_id} for task {checkpoint.task_id}")

    def load(self, task_id: str, checkpoint_id: str) -> Checkpoint | None:
        """Load a checkpoint by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT checkpoint_id, node_name, timestamp, full_state, parent_checkpoint_id
            FROM checkpoints
            WHERE task_id = ? AND checkpoint_id = ?
        """, (task_id, checkpoint_id))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return Checkpoint(
            task_id=task_id,
            checkpoint_id=row[0],
            node_name=row[1],
            timestamp=datetime.fromisoformat(row[2]),
            full_state=GraphState.from_json(row[3]) if row[3] else None,
            parent_checkpoint_id=row[4],
        )

    def get_latest(self, task_id: str) -> Checkpoint | None:
        """Get the latest checkpoint for a task."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT checkpoint_id, node_name, timestamp, full_state, parent_checkpoint_id
            FROM checkpoints
            WHERE task_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (task_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return Checkpoint(
            task_id=task_id,
            checkpoint_id=row[0],
            node_name=row[1],
            timestamp=datetime.fromisoformat(row[2]),
            full_state=GraphState.from_json(row[3]) if row[3] else None,
            parent_checkpoint_id=row[4],
        )

    def get_all(self, task_id: str) -> list[Checkpoint]:
        """Get all checkpoints for a task."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT checkpoint_id, node_name, timestamp, full_state, parent_checkpoint_id
            FROM checkpoints
            WHERE task_id = ?
            ORDER BY timestamp ASC
        """, (task_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            Checkpoint(
                task_id=task_id,
                checkpoint_id=row[0],
                node_name=row[1],
                timestamp=datetime.fromisoformat(row[2]),
                full_state=GraphState.from_json(row[3]) if row[3] else None,
                parent_checkpoint_id=row[4],
            )
            for row in rows
        ]

    def delete(self, task_id: str, checkpoint_id: str) -> None:
        """Delete a checkpoint."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM checkpoints
            WHERE task_id = ? AND checkpoint_id = ?
        """, (task_id, checkpoint_id))
        
        conn.commit()
        conn.close()


class Checkpointer:
    """
    Checkpoint manager for graph execution.
    
    Provides:
    - Auto-save after each node execution
    - Resume from latest checkpoint
    - Resume from specific checkpoint
    - Inspect state at any point
    """

    def __init__(self, storage: CheckpointStorage | None = None, storage_dir: Path | str | None = None):
        if storage:
            self.storage = storage
        elif storage_dir:
            self.storage = JsonCheckpointStorage(storage_dir)
        else:
            self.storage = JsonCheckpointStorage("./workspace/graph_checkpoints")

    def save_checkpoint(self, state: GraphState, node_name: str, parent_checkpoint_id: str | None = None) -> Checkpoint:
        """Save a checkpoint after node execution."""
        checkpoint = Checkpoint(
            task_id=state.task_id,
            node_name=node_name,
            full_state=state,
            parent_checkpoint_id=parent_checkpoint_id,
        )
        self.storage.save(checkpoint)
        return checkpoint

    def resume_from_latest(self, task_id: str) -> GraphState | None:
        """Resume execution from the latest checkpoint."""
        checkpoint = self.storage.get_latest(task_id)
        
        if checkpoint and checkpoint.full_state:
            logger.info(f"[Checkpointer] Resuming task {task_id} from checkpoint {checkpoint.checkpoint_id}")
            return checkpoint.full_state
        
        return None

    def resume_from_checkpoint(self, task_id: str, checkpoint_id: str) -> GraphState | None:
        """Resume execution from a specific checkpoint."""
        checkpoint = self.storage.load(task_id, checkpoint_id)
        
        if checkpoint and checkpoint.full_state:
            logger.info(f"[Checkpointer] Resuming task {task_id} from checkpoint {checkpoint_id}")
            return checkpoint.full_state
        
        return None

    def inspect_state(self, task_id: str) -> list[Checkpoint]:
        """Inspect all checkpoints for a task."""
        return self.storage.get_all(task_id)

    def get_latest_checkpoint_info(self, task_id: str) -> dict | None:
        """Get latest checkpoint info without loading full state."""
        checkpoint = self.storage.get_latest(task_id)
        
        if not checkpoint:
            return None
        
        return {
            "task_id": checkpoint.task_id,
            "checkpoint_id": checkpoint.checkpoint_id,
            "node_name": checkpoint.node_name,
            "timestamp": checkpoint.timestamp.isoformat(),
            "current_step": checkpoint.full_state.current_step if checkpoint.full_state else 0,
            "status": checkpoint.full_state.status.value if checkpoint.full_state else "unknown",
        }


__all__ = [
    "Checkpoint",
    "CheckpointStorage",
    "JsonCheckpointStorage",
    "SQLiteCheckpointStorage",
    "Checkpointer",
]
