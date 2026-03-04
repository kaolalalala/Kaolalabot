"""Graph Runtime - Diagnoser and Recovery Nodes."""

from __future__ import annotations

from loguru import logger

from kaolalabot.graph.nodes.base import BaseNode, NodeResult
from kaolalabot.graph.state import ErrorType, GraphState


class DiagnoserNode(BaseNode):
    """
    Diagnoser node: classifies errors and determines recovery strategy.
    """

    def __init__(self, **kwargs):
        super().__init__(name="diagnoser", purpose="Classify errors and determine recovery", **kwargs)

    async def execute(self, state: GraphState) -> NodeResult:
        """Execute diagnosis."""
        logger.info(f"[Diagnoser] Analyzing errors at step {state.current_step}")

        if not state.errors:
            return NodeResult(
                state=state,
                success=True,
                next_node="recovery",
            )

        latest_error = state.errors[-1]
        error_type = self._classify_error(latest_error)
        
        logger.info(f"[Diagnoser] Classified error type: {error_type.value}")

        state.errors[-1]["classified_type"] = error_type.value

        recovery_strategy = self._get_recovery_strategy(error_type)

        return NodeResult(
            state=state,
            success=True,
            next_node="recovery",
            recovery_strategy=recovery_strategy,
        )

    def _classify_error(self, error: dict) -> ErrorType:
        """Classify error type based on error message."""
        message = error.get("message", "").lower()
        
        if any(kw in message for kw in ["timeout", "429", "rate limit", "connection", "network", "temporarily"]):
            return ErrorType.TRANSIENT
        elif any(kw in message for kw in ["invalid", "format", "missing", "schema", "validation"]):
            return ErrorType.VALIDATION
        elif any(kw in message for kw in ["not found", "path", "file", "directory", "environment"]):
            return ErrorType.ENVIRONMENT
        elif any(kw in message for kw in ["understand", "intent", "goal", "plan", "reasoning"]):
            return ErrorType.REASONING
        elif any(kw in message for kw in ["token", "length", "context", "memory", "too long", "cost"]):
            return ErrorType.RESOURCE
        elif any(kw in message for kw in ["loop", "repeat", "same", "again", "stuck"]):
            return ErrorType.LOOP
        
        return ErrorType.UNKNOWN

    def _get_recovery_strategy(self, error_type: ErrorType) -> str:
        """Get recovery strategy based on error type."""
        strategies = {
            ErrorType.TRANSIENT: "retry_with_backoff",
            ErrorType.VALIDATION: "reformat_and_retry",
            ErrorType.ENVIRONMENT: "recover_environment",
            ErrorType.REASONING: "replan",
            ErrorType.RESOURCE: "summarize_and_continue",
            ErrorType.LOOP: "escalate_to_human",
            ErrorType.UNKNOWN: "retry",
        }
        return strategies.get(error_type, "retry")


class RecoveryNode(BaseNode):
    """
    Recovery node: executes recovery based on strategy.
    """

    def __init__(self, llm_provider=None, **kwargs):
        super().__init__(name="recovery", purpose="Execute recovery strategy", **kwargs)
        self.llm_provider = llm_provider

    async def execute(self, state: GraphState) -> NodeResult:
        """Execute recovery."""
        logger.info(f"[Recovery] Executing recovery at step {state.current_step}")

        if not state.errors:
            return NodeResult(
                state=state,
                success=True,
                next_node="executor",
            )

        latest_error = state.errors[-1]
        strategy = latest_error.get("recovery_strategy", "retry")
        
        logger.info(f"[Recovery] Using strategy: {strategy}")

        state.retry_count += 1

        if strategy == "replan":
            return NodeResult(
                state=state,
                success=True,
                next_node="planner",
            )
        elif strategy == "summarize_and_continue":
            return NodeResult(
                state=state,
                success=True,
                next_node="summarizer",
            )
        elif strategy == "escalate_to_human":
            state.human_review_required = True
            state.status = ErrorType.__class__.__name__
            return NodeResult(
                state=state,
                success=False,
                error="Loop detected, human review required",
                error_type=ErrorType.LOOP,
                human_review=True,
            )
        else:
            current_subtask = state.get_current_subtask()
            if current_subtask:
                current_subtask.status = "pending"
                state.current_subtask_id = current_subtask.id
            
            return NodeResult(
                state=state,
                success=True,
                next_node="executor",
            )
