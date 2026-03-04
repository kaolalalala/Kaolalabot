"""Graph Runtime - Executor Node."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from kaolalabot.graph.nodes.base import BaseNode, NodeResult
from kaolalabot.graph.state import ErrorType, GraphState, SubTaskStatus


class ExecutorNode(BaseNode):
    """
    Executor node: executes current subtask using tools.
    
    Uses the existing AgentLoop's tool execution capability.
    """

    def __init__(self, agent_loop=None, tool_registry=None, llm_provider=None, **kwargs):
        super().__init__(name="executor", purpose="Execute current subtask", **kwargs)
        self.agent_loop = agent_loop
        self.tool_registry = tool_registry
        self.llm_provider = llm_provider
        self._messages: list[dict] = []

    async def execute(self, state: GraphState) -> NodeResult:
        """Execute the current subtask."""
        logger.info(f"[Executor] Executing subtask at step {state.current_step}")

        current_subtask = state.get_current_subtask()
        
        if not current_subtask:
            failed = state.get_failed_subtasks()
            if failed:
                return NodeResult(
                    state=state,
                    success=False,
                    error="No running subtask found after failures",
                    error_type=ErrorType.REASONING,
                    should_recover=True,
                    recovery_strategy="replan",
                )
            return NodeResult(
                state=state,
                success=True,
                next_node="finalizer",
            )

        logger.info(f"[Executor] Running: {current_subtask.objective}")

        if self.llm_provider and self.tool_registry:
            result = await self._execute_with_llm(state, current_subtask.objective)
        elif self.agent_loop:
            result = await self._execute_with_agent(state, current_subtask.objective)
        else:
            result = f"Executed: {current_subtask.objective}"

        current_subtask.result = result
        current_subtask.status = SubTaskStatus.DONE
        
        state.mark_subtask_done(current_subtask.id, result)

        next_pending = state.get_pending_subtasks()
        if next_pending:
            state.current_subtask_id = next_pending[0].id
            next_pending[0].status = SubTaskStatus.RUNNING
            return NodeResult(
                state=state,
                success=True,
                next_node="verifier",
            )
        else:
            return NodeResult(
                state=state,
                success=True,
                next_node="finalizer",
            )

    async def _execute_with_llm(self, state: GraphState, objective: str) -> str:
        """Execute using LLM with tools."""
        failed_tasks = state.get_failed_subtasks()
        context = ""
        if failed_tasks:
            context = f"\n\nPrevious failed attempts:\n"
            for t in failed_tasks:
                context += f"- {t.objective}: {t.error}\n"

        prompt = f"""You are executing a subtask as part of a larger goal.

Current Goal: {state.goal}
Current Subtask: {objective}
Expected Output: {state.get_current_subtask().expected_output if state.get_current_subtask() else 'N/A'}

{context}

Execute this subtask using available tools. If you need to call tools, call them one at a time.
After completing the task, provide a summary of what was done and the result.
"""

        try:
            messages = [{"role": "user", "content": prompt}]
            
            response = await self.llm_provider.chat(
                messages=messages,
                tools=self.tool_registry.get_definitions() if self.tool_registry else [],
                model=state.metadata.get("model", None),
                temperature=0.1,
                max_tokens=4096,
            )

            if response.has_tool_calls:
                for tc in response.tool_calls:
                    args_str = json.dumps(tc.arguments, ensure_ascii=False)
                    logger.info(f"[Executor] Tool: {tc.name}({args_str[:100]}...)")
                    result = await self.tool_registry.execute(tc.name, tc.arguments) if self.tool_registry else "No tool registry"
                    
                    state.tool_history.append({
                        "tool": tc.name,
                        "arguments": tc.arguments,
                        "result": str(result)[:500],
                        "timestamp": self._get_timestamp(),
                    })
                    
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": args_str
                            }
                        }]
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result),
                    })
                
                final_response = await self.llm_provider.chat(
                    messages=messages,
                    model=state.metadata.get("model", None),
                    temperature=0.1,
                    max_tokens=1024,
                )
                return final_response.content or "Task completed"
            
            return response.content or "Task completed"
            
        except Exception as e:
            logger.error(f"[Executor] Execution failed: {e}")
            return f"Error: {str(e)}"

    async def _execute_with_agent(self, state: GraphState, objective: str) -> str:
        """Execute using the agent loop."""
        try:
            result = await self.agent_loop.process_direct(
                content=objective,
                session_key=f"graph:{state.task_id}",
                on_progress=lambda x: logger.debug(f"[Executor] Progress: {x}"),
            )
            return result
        except Exception as e:
            logger.error(f"[Executor] Agent execution failed: {e}")
            return f"Error: {str(e)}"

    def _get_timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().isoformat()
