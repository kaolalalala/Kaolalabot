"""Graph Runtime - Summarizer, HumanGate, and Finalizer Nodes."""

from __future__ import annotations

from loguru import logger

from kaolalabot.graph.nodes.base import BaseNode, NodeResult
from kaolalabot.graph.state import ErrorType, GraphState, TaskStatus


class SummarizerNode(BaseNode):
    """
    Summarizer node: compresses context to avoid state bloat.
    
    Reduces node_history and tool_history while preserving key information.
    """

    def __init__(self, llm_provider=None, **kwargs):
        super().__init__(name="summarizer", purpose="Compress context to avoid state bloat", **kwargs)
        self.llm_provider = llm_provider

    async def execute(self, state: GraphState) -> NodeResult:
        """Execute summarization."""
        logger.info(f"[Summarizer] Compressing context at step {state.current_step}")

        original_history_len = len(state.node_history)
        original_tool_len = len(state.tool_history)

        if self.llm_provider and (len(state.node_history) > 10 or len(state.tool_history) > 20):
            summary = await self._llm_summarize(state)
            state.artifacts["context_summary"] = summary
            state.node_history = state.node_history[-5:]
            state.tool_history = state.tool_history[-10:]
        else:
            state.node_history = state.node_history[-10:] if state.node_history else []
            state.tool_history = state.tool_history[-20:] if state.tool_history else []

        logger.info(f"[Summarizer] Compressed {original_history_len} -> {len(state.node_history)} node entries, "
                   f"{original_tool_len} -> {len(state.tool_history)} tool entries")

        state.metadata["last_summarized_at"] = self._get_timestamp()

        return NodeResult(
            state=state,
            success=True,
            next_node="executor",
        )

    async def _llm_summarize(self, state: GraphState) -> str:
        """Use LLM to generate context summary."""
        prompt = f"""Summarize the execution history concisely:

Goal: {state.goal}

Recent Node History:
{self._format_history(state.node_history[-10:])}

Recent Tool History:
{self._format_tools(state.tool_history[-20:])}

Provide a concise summary of:
1. What has been accomplished so far
2. Current progress (which subtask)
3. Any errors encountered
4. Key decisions made

Keep it under 200 words.
"""

        try:
            response = await self.llm_provider.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
            return response.content or ""
        except Exception as e:
            logger.error(f"[Summarizer] LLM summarization failed: {e}")
            return f"Error summarization: {e}"

    def _format_history(self, history: list[dict]) -> str:
        if not history:
            return "  (none)"
        lines = []
        for h in history:
            status = "✓" if h.get("success") else "✗"
            lines.append(f"  {status} {h.get('node')}: {h.get('elapsed_ms')}ms")
        return "\n".join(lines)

    def _format_tools(self, tools: list[dict]) -> str:
        if not tools:
            return "  (none)"
        lines = []
        for t in tools:
            lines.append(f"  - {t.get('tool')}: {str(t.get('arguments', {}))[:50]}")
        return "\n".join(lines)

    def _get_timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().isoformat()


class HumanGateNode(BaseNode):
    """
    HumanGate node: requires human review before continuing.
    
    Pauses execution and waits for human input.
    """

    def __init__(self, **kwargs):
        super().__init__(name="human_gate", purpose="Require human review before continuing", **kwargs)

    async def execute(self, state: GraphState) -> NodeResult:
        """Execute human gate."""
        logger.info(f"[HumanGate] Pausing for human review at step {state.current_step}")

        state.human_review_required = True
        state.status = TaskStatus.PAUSED

        review_info = {
            "current_node": "human_gate",
            "goal": state.goal,
            "current_subtask": state.get_current_subtask().objective if state.get_current_subtask() else None,
            "errors": state.errors[-3:] if state.errors else [],
            "node_history_summary": state.node_history[-5:] if state.node_history else [],
            "suggested_actions": self._get_suggestions(state),
        }

        state.artifacts["human_review_info"] = review_info

        return NodeResult(
            state=state,
            success=False,
            error="Human review required",
            human_review=True,
        )

    def _get_suggestions(self, state: GraphState) -> list[str]:
        """Get suggested actions based on state."""
        suggestions = []
        
        if state.retry_count > 5:
            suggestions.append("Reset the task and start fresh")
        
        if any(e.get("type") == ErrorType.LOOP.value for e in state.errors[-3:]):
            suggestions.append("The agent is stuck in a loop - consider breaking down the task")
        
        if any(e.get("type") == ErrorType.REASONING.value for e in state.errors[-3:]):
            suggestions.append("The agent misunderstood the goal - clarify the objective")
        
        if not suggestions:
            suggestions = [
                "Continue execution",
                "Modify the goal",
                "Reset and restart",
            ]
        
        return suggestions


class FinalizerNode(BaseNode):
    """
    Finalizer node: summarizes final result and marks task as complete.
    """

    def __init__(self, llm_provider=None, **kwargs):
        super().__init__(name="finalizer", purpose="Finalize and summarize results", **kwargs)
        self.llm_provider = llm_provider

    async def execute(self, state: GraphState) -> NodeResult:
        """Execute finalization."""
        logger.info(f"[Finalizer] Finalizing at step {state.current_step}")

        completed_subtasks = [s for s in state.plan if s.status.value == "done"]
        
        final_summary = await self._generate_summary(state, completed_subtasks)

        state.artifacts["final_summary"] = final_summary
        state.status = TaskStatus.FINISHED
        
        logger.info(f"[Finalizer] Task completed with {len(completed_subtasks)} subtasks")

        return NodeResult(
            state=state,
            success=True,
        )

    async def _generate_summary(self, state: GraphState, completed: list) -> str:
        """Generate final summary."""
        if not self.llm_provider:
            return f"Completed {len(completed)} subtasks for goal: {state.goal}"

        prompt = f"""Generate a final summary for the user.

Goal: {state.goal}

Completed Subtasks:
{self._format_subtasks(completed)}

Errors encountered: {len(state.errors)}

Provide a concise summary of what was accomplished.
"""

        try:
            response = await self.llm_provider.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
            return response.content or f"Completed {len(completed)} subtasks"
        except Exception as e:
            return f"Completed {len(completed)} subtasks (summary generation failed: {e})"

    def _format_subtasks(self, subtasks: list) -> str:
        if not subtasks:
            return "  (none)"
        lines = []
        for s in subtasks:
            lines.append(f"  - {s.objective}: {str(s.result)[:100]}")
        return "\n".join(lines)
