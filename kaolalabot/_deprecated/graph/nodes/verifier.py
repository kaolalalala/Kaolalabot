"""Graph Runtime - Verifier Node."""

from __future__ import annotations

from loguru import logger

from kaolalabot.graph.nodes.base import BaseNode, NodeResult
from kaolalabot.graph.state import ErrorType, GraphState


class VerifierNode(BaseNode):
    """
    Verifier node: checks if current subtask result meets expectations.
    
    Uses LLM to verify if the result is acceptable.
    """

    def __init__(self, llm_provider=None, **kwargs):
        super().__init__(name="verifier", purpose="Verify subtask result meets expectations", **kwargs)
        self.llm_provider = llm_provider

    async def execute(self, state: GraphState) -> NodeResult:
        """Execute verification."""
        logger.info(f"[Verifier] Verifying subtask result at step {state.current_step}")

        current_subtask = state.get_current_subtask()
        
        if not current_subtask:
            return NodeResult(
                state=state,
                success=True,
                next_node="finalizer",
            )

        result = current_subtask.result
        expected = current_subtask.expected_output

        if not result:
            return NodeResult(
                state=state,
                success=False,
                error=f"No result to verify for subtask {current_subtask.id}",
                error_type=ErrorType.VALIDATION,
                should_recover=True,
                recovery_strategy="retry",
            )

        if self.llm_provider:
            is_valid = await self._llm_verify(state, current_subtask, result)
        else:
            is_valid = self._simple_verify(result, expected)

        if is_valid:
            logger.info(f"[Verifier] Subtask {current_subtask.id} verified successfully")
            return NodeResult(
                state=state,
                success=True,
                next_node="executor",
            )
        else:
            logger.warning(f"[Verifier] Subtask {current_subtask.id} verification failed")
            return NodeResult(
                state=state,
                success=False,
                error=f"Result does not meet expectations: {expected}",
                error_type=ErrorType.VALIDATION,
                should_recover=True,
                recovery_strategy="replan",
            )

    async def _llm_verify(self, state: GraphState, subtask, result: str) -> bool:
        """Use LLM to verify result."""
        prompt = f"""You are verifying if a subtask result meets expectations.

Goal: {state.goal}
Subtask: {subtask.objective}
Expected Output: {subtask.expected_output}
Actual Result: {result}

Evaluate whether the result satisfies the expected output.
Consider:
1. Does the result address the subtask objective?
2. Is the output format correct?
3. Are there any obvious errors or missing components?

Respond with ONLY "PASS" or "FAIL" followed by a brief reason.
Example: "PASS - The file was created successfully with correct content"
Example: "FAIL - The result is empty, expected file content"
"""

        try:
            response = await self.llm_provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=state.metadata.get("model", None),
                temperature=0.1,
                max_tokens=200,
            )
            
            content = (response.content or "").strip().upper()
            return content.startswith("PASS")
            
        except Exception as e:
            logger.error(f"[Verifier] LLM verification failed: {e}")
            return self._simple_verify(result, subtask.expected_output)

    def _simple_verify(self, result: str, expected: str | None) -> bool:
        """Simple rule-based verification."""
        if not result:
            return False
        
        result_lower = result.lower()
        
        if "error" in result_lower or "failed" in result_lower:
            return False
        
        if expected:
            expected_lower = expected.lower()
            expected_keywords = [w for w in expected_lower.split() if len(w) > 3]
            if expected_keywords:
                matches = sum(1 for kw in expected_keywords if kw in result_lower)
                return matches >= len(expected_keywords) * 0.5
        
        return len(result) > 10
