"""Graph Runtime - Base Node and Node Registry."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from loguru import logger

from kaolalabot.graph.state import ErrorType, GraphState


@dataclass
class NodeMetadata:
    """Metadata for a node."""
    name: str
    purpose: str
    input_requirements: list[str] = field(default_factory=list)
    possible_failure_modes: list[str] = field(default_factory=list)
    retryable: bool = True
    max_retries: int = 3


class NodeResult:
    """Result from node execution."""
    
    def __init__(
        self,
        state: GraphState,
        success: bool = True,
        next_node: str | None = None,
        error: str | None = None,
        error_type: ErrorType | None = None,
        should_retry: bool = False,
        should_recover: bool = False,
        recovery_strategy: str | None = None,
        human_review: bool = False,
    ):
        self.state = state
        self.success = success
        self.next_node = next_node
        self.error = error
        self.error_type = error_type
        self.should_retry = should_retry
        self.should_recover = should_recover
        self.recovery_strategy = recovery_strategy
        self.human_review = human_review


class BaseNode(ABC):
    """
    Abstract base class for all nodes in the graph.
    
    Each node is a single-responsibility execution unit.
    Input: GraphState
    Output: NodeResult with updated state and routing decision
    """

    def __init__(self, name: str, purpose: str, retryable: bool = True, max_retries: int = 3):
        self.name = name
        self.metadata = NodeMetadata(
            name=name,
            purpose=purpose,
            retryable=retryable,
            max_retries=max_retries,
        )
        self._retry_count = 0

    @abstractmethod
    async def execute(self, state: GraphState) -> NodeResult:
        """
        Execute the node logic.
        
        Args:
            state: The current graph state
            
        Returns:
            NodeResult with updated state and routing decision
        """
        pass

    async def pre_execute(self, state: GraphState) -> GraphState:
        """Hook called before execution. Can modify state."""
        return state

    async def post_execute(self, state: GraphState, result: NodeResult) -> NodeResult:
        """Hook called after execution. Can modify result."""
        return result

    def can_retry(self) -> bool:
        """Check if node can be retried."""
        return self.metadata.retryable and self._retry_count < self.metadata.max_retries

    def increment_retry(self) -> None:
        """Increment retry counter."""
        self._retry_count += 1

    def reset_retry(self) -> None:
        """Reset retry counter."""
        self._retry_count = 0

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"


class NodeRegistry:
    """Registry for all available nodes."""

    _nodes: dict[str, type[BaseNode]] = {}

    @classmethod
    def register(cls, node_class: type[BaseNode]) -> type[BaseNode]:
        """Register a node class."""
        cls._nodes[node_class.__name__] = node_class
        return node_class

    @classmethod
    def get(cls, name: str) -> type[BaseNode] | None:
        """Get a node class by name."""
        return cls._nodes.get(name)

    @classmethod
    def list_nodes(cls) -> list[str]:
        """List all registered node names."""
        return list(cls._nodes.keys())

    @classmethod
    def create(cls, name: str, **kwargs) -> BaseNode | None:
        """Create a node instance by name."""
        node_class = cls._nodes.get(name)
        if node_class:
            return node_class(**kwargs)
        return None
