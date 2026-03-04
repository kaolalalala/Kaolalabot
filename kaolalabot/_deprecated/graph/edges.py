"""Graph Runtime - Edge Routing Mechanism."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from loguru import logger

from kaolalabot.graph.state import ErrorType, GraphState, TaskStatus


class RouteDecision(str, Enum):
    """Routing decision types."""
    CONTINUE = "continue"
    JUMP = "jump"
    LOOP = "loop"
    END = "end"
    PAUSE = "pause"
    FAIL = "fail"


@dataclass
class Edge:
    """
    Edge in the execution graph.
    
    Defines a connection between two nodes with optional condition.
    """
    source: str
    target: str
    condition: Callable[[GraphState], bool] | None = None
    name: str = ""
    description: str = ""

    def __post_init__(self):
        if not self.name:
            self.name = f"{self.source}->{self.target}"

    def can_traverse(self, state: GraphState) -> bool:
        """Check if this edge can be traversed given current state."""
        if self.condition is None:
            return True
        try:
            return self.condition(state)
        except Exception as e:
            logger.warning(f"Edge condition failed: {e}")
            return False


class Router:
    """
    Router determines next node based on current state.
    
    Supports:
    - Fixed jumps
    - Conditional jumps
    - Loops
    - Circuit breaker (fuse)
    """

    def __init__(self, nodes: dict[str, Any]):
        self.nodes = nodes
        self.edges: list[Edge] = []
        self._circuit_breaker_failures = 0
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_state = "closed"

    def add_edge(self, edge: Edge) -> "Router":
        """Add an edge to the router."""
        self.edges.append(edge)
        return self

    def add_fixed(self, source: str, target: str) -> "Router":
        """Add a fixed jump edge."""
        self.edges.append(Edge(source=source, target=target))
        return self

    def add_conditional(
        self,
        source: str,
        target: str,
        condition: Callable[[GraphState], bool],
        description: str = "",
    ) -> "Router":
        """Add a conditional edge."""
        self.edges.append(Edge(
            source=source,
            target=target,
            condition=condition,
            description=description,
        ))
        return self

    def get_next_node(self, current_node: str, state: GraphState) -> tuple[str, RouteDecision]:
        """
        Determine next node based on current state.
        
        Returns:
            tuple of (next_node_name, route_decision)
        """
        applicable_edges = [e for e in self.edges if e.source == current_node]
        
        if not applicable_edges:
            return current_node, RouteDecision.END

        for edge in applicable_edges:
            if edge.can_traverse(state):
                if edge.target == current_node:
                    return edge.target, RouteDecision.LOOP
                return edge.target, RouteDecision.CONTINUE

        return current_node, RouteDecision.END

    def check_circuit_breaker(self, state: GraphState) -> bool:
        """Check if circuit breaker should trip."""
        recent_errors = state.errors[-3:] if state.errors else []
        
        if len(recent_errors) >= self._circuit_breaker_threshold:
            same_type = all(e.get("type") == recent_errors[0].get("type") for e in recent_errors)
            if same_type:
                self._circuit_breaker_state = "open"
                logger.warning("[Router] Circuit breaker opened due to repeated failures")
                return True
        
        return False

    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker."""
        self._circuit_breaker_state = "closed"
        self._circuit_breaker_failures = 0


def create_default_edges() -> list[Edge]:
    """Create default execution graph edges."""
    edges = [
        Edge(source="planner", target="executor"),
        Edge(source="executor", target="verifier"),
        Edge(
            source="verifier",
            target="executor",
            condition=lambda s: len(s.get_failed_subtasks()) == 0 and len(s.get_pending_subtasks()) > 0,
            description="If verification passed and more tasks",
        ),
        Edge(
            source="verifier",
            target="diagnoser",
            condition=lambda s: len(s.errors) > 0 and s.errors[-1].get("success", True) == False,
            description="If verification failed",
        ),
        Edge(source="diagnoser", target="recovery"),
        Edge(
            source="recovery",
            target="planner",
            condition=lambda s: s.errors[-1].get("recovery_strategy") == "replan" if s.errors else False,
            description="If recovery needs replanning",
        ),
        Edge(
            source="recovery",
            target="summarizer",
            condition=lambda s: s.errors[-1].get("recovery_strategy") == "summarize_and_continue" if s.errors else False,
            description="If recovery needs summarization",
        ),
        Edge(
            source="recovery",
            target="executor",
            condition=lambda s: s.errors[-1].get("recovery_strategy") in ["retry", "retry_with_backoff", "recover_environment"] if s.errors else True,
            description="Default: retry execution",
        ),
        Edge(
            source="summarizer",
            target="executor",
            description="After summarization, continue execution",
        ),
        Edge(
            source="verifier",
            target="finalizer",
            condition=lambda s: len(s.get_pending_subtasks()) == 0 and len(s.get_failed_subtasks()) == 0,
            description="All tasks completed",
        ),
        Edge(source="diagnoser", target="human_gate"),
    ]
    return edges


class SimpleRouter:
    """
    Simplified router for basic graph execution.
    
    Maps node names to their next nodes based on result.
    """

    DEFAULT_ROUTES = {
        "planner": "executor",
        "executor": "verifier",
        "verifier": {
            True: "executor",
            False: "diagnoser",
        },
        "diagnoser": "recovery",
        "recovery": "executor",
        "summarizer": "executor",
        "human_gate": "executor",
        "finalizer": None,
    }

    def __init__(self, routes: dict | None = None):
        self.routes = routes or self.DEFAULT_ROUTES

    def get_next(self, current_node: str, success: bool | None = None, state: GraphState | None = None) -> str | None:
        """Get next node based on current node and success status."""
        route = self.routes.get(current_node)
        
        if route is None:
            return None
        
        if isinstance(route, dict):
            key = success if success is not None else True
            return route.get(key)
        
        if callable(route):
            return route(state) if state else route()
        
        return route


__all__ = [
    "Edge",
    "Router",
    "SimpleRouter",
    "RouteDecision",
    "create_default_edges",
]
