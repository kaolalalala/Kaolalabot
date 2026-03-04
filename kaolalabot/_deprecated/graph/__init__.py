"""Graph Runtime - LangGraph-style execution framework for Kaolalabot.

This module provides:
- State: Shared state management with JSON serialization
- Nodes: Pluggable execution units (planner, executor, verifier, etc.)
- Edges: Conditional routing between nodes
- Checkpoint: Persistence for recovery and time-travel
- Runtime: Core execution loop with error handling

Quick Start:
    from kaolalabot.graph import GraphRuntime, GraphState
    
    runtime = GraphRuntime()
    state = await runtime.run("Your goal here")
"""

from kaolalabot.graph.state import (
    GraphState,
    TaskStatus,
    ErrorType,
    SubTask,
    SubTaskStatus,
)

from kaolalabot.graph.nodes.base import (
    BaseNode,
    NodeResult,
    NodeRegistry,
)

from kaolalabot.graph.nodes import (
    PlannerNode,
    ExecutorNode,
    VerifierNode,
    DiagnoserNode,
    RecoveryNode,
    SummarizerNode,
    HumanGateNode,
    FinalizerNode,
    create_default_graph,
    register_all_nodes,
)

from kaolalabot.graph.edges import (
    Edge,
    Router,
    SimpleRouter,
    RouteDecision,
    create_default_edges,
)

from kaolalabot.graph.checkpoint import (
    Checkpoint,
    CheckpointStorage,
    JsonCheckpointStorage,
    SQLiteCheckpointStorage,
    Checkpointer,
)

from kaolalabot.graph.runtime import (
    GraphRuntime,
    RuntimeStatus,
    ExecutionEvent,
)

register_all_nodes()

__all__ = [
    "GraphState",
    "TaskStatus",
    "ErrorType",
    "SubTask",
    "SubTaskStatus",
    "BaseNode",
    "NodeResult",
    "NodeRegistry",
    "PlannerNode",
    "ExecutorNode",
    "VerifierNode",
    "DiagnoserNode",
    "RecoveryNode",
    "SummarizerNode",
    "HumanGateNode",
    "FinalizerNode",
    "create_default_graph",
    "register_all_nodes",
    "Edge",
    "Router",
    "SimpleRouter",
    "RouteDecision",
    "create_default_edges",
    "Checkpoint",
    "CheckpointStorage",
    "JsonCheckpointStorage",
    "SQLiteCheckpointStorage",
    "Checkpointer",
    "GraphRuntime",
    "RuntimeStatus",
    "ExecutionEvent",
]
