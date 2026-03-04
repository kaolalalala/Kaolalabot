"""Graph Runtime - Node Factory and Registry."""

from __future__ import annotations

from kaolalabot.graph.nodes.base import BaseNode, NodeRegistry
from kaolalabot.graph.nodes.planner import PlannerNode
from kaolalabot.graph.nodes.executor import ExecutorNode
from kaolalabot.graph.nodes.verifier import VerifierNode
from kaolalabot.graph.nodes.diagnoser import DiagnoserNode, RecoveryNode
from kaolalabot.graph.nodes.finalizer import SummarizerNode, HumanGateNode, FinalizerNode


def register_all_nodes():
    """Register all built-in nodes."""
    NodeRegistry.register(PlannerNode)
    NodeRegistry.register(ExecutorNode)
    NodeRegistry.register(VerifierNode)
    NodeRegistry.register(DiagnoserNode)
    NodeRegistry.register(RecoveryNode)
    NodeRegistry.register(SummarizerNode)
    NodeRegistry.register(HumanGateNode)
    NodeRegistry.register(FinalizerNode)


def create_default_graph(llm_provider=None, agent_loop=None, tool_registry=None) -> dict[str, BaseNode]:
    """Create the default execution graph with nodes."""
    return {
        "planner": PlannerNode(llm_provider=llm_provider),
        "executor": ExecutorNode(llm_provider=llm_provider, agent_loop=agent_loop, tool_registry=tool_registry),
        "verifier": VerifierNode(llm_provider=llm_provider),
        "diagnoser": DiagnoserNode(),
        "recovery": RecoveryNode(llm_provider=llm_provider),
        "summarizer": SummarizerNode(llm_provider=llm_provider),
        "human_gate": HumanGateNode(),
        "finalizer": FinalizerNode(llm_provider=llm_provider),
    }


__all__ = [
    "BaseNode",
    "NodeRegistry",
    "PlannerNode",
    "ExecutorNode",
    "VerifierNode",
    "DiagnoserNode",
    "RecoveryNode",
    "SummarizerNode",
    "HumanGateNode",
    "FinalizerNode",
    "register_all_nodes",
    "create_default_graph",
]
