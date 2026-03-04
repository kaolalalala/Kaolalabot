"""Graph Runtime - Planner Node."""

from __future__ import annotations

import uuid
from typing import Any

from loguru import logger

from kaolalabot.graph.nodes.base import BaseNode, NodeResult
from kaolalabot.graph.state import ErrorType, GraphState, SubTask, SubTaskStatus


class PlannerNode(BaseNode):
    """
    Planner node: generates or updates execution plan.
    
    First call: breaks goal into subtask list.
    Subsequent calls: can rewrite failed subtasks and their dependencies.
    """

    def __init__(self, llm_provider=None, **kwargs):
        super().__init__(name="planner", purpose="Generate or update execution plan", **kwargs)
        self.llm_provider = llm_provider

    async def execute(self, state: GraphState) -> NodeResult:
        """Execute planning."""
        logger.info(f"[Planner] Planning for task: {state.goal[:50]}...")

        if not state.goal:
            return NodeResult(
                state=state,
                success=False,
                error="No goal provided",
                error_type=ErrorType.REASONING,
            )

        if self.llm_provider:
            plan = await self._llm_plan(state)
        else:
            plan = self._simple_plan(state)

        state.plan = plan
        
        pending = state.get_pending_subtasks()
        if pending:
            state.current_subtask_id = pending[0].id
            pending[0].status = SubTaskStatus.RUNNING

        logger.info(f"[Planner] Generated {len(plan)} subtasks")
        
        return NodeResult(
            state=state,
            success=True,
            next_node="executor",
        )

    async def _llm_plan(self, state: GraphState) -> list[SubTask]:
        """Use LLM to generate plan."""
        failed_subtasks = state.get_failed_subtasks()
        
        if failed_subtasks:
            prompt = f"""The user goal is: {state.goal}

Previous plan had these failed subtasks:
{self._format_subtasks(failed_subtasks)}

Errors:
{self._format_errors(failed_subtasks)}

Please revise ONLY the failed subtasks and their dependent tasks. 
Output a JSON list of subtasks with fields: id, objective, expected_output, dependencies, status (always 'pending').
"""
        else:
            prompt = f"""Break down this user goal into executable subtasks:

User Goal: {state.goal}

Consider:
- Break into logical steps
- Each subtask should be atomic and verifiable
- Consider dependencies between subtasks

Output a JSON list of subtasks with fields: id, objective, expected_output, dependencies, status (always 'pending').
"""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm_provider.chat(
                messages=messages,
                model=state.metadata.get("model", None),
                temperature=0.3,
                max_tokens=2000,
            )
            
            import json
            import re
            
            content = response.content or ""
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                plan_data = json.loads(json_match.group())
                return [SubTask(**item) for item in plan_data]
        except Exception as e:
            logger.warning(f"[Planner] LLM planning failed: {e}")

        return self._simple_plan(state)

    def _simple_plan(self, state: GraphState) -> list[SubTask]:
        """Simple rule-based planning."""
        goal = state.goal.lower()
        
        if "file" in goal or "read" in goal or "write" in goal or "create" in goal:
            subtasks = [
                SubTask(id=str(uuid.uuid4())[:8], objective="Analyze the task and identify required file operations", expected_output="List of file operations"),
                SubTask(id=str(uuid.uuid4())[:8], objective="Execute the identified file operations", expected_output="Operation results"),
                SubTask(id=str(uuid.uuid4())[:8], objective="Verify the operations completed successfully", expected_output="Verification result"),
            ]
        elif "search" in goal or "find" in goal or "look" in goal:
            subtasks = [
                SubTask(id=str(uuid.uuid4())[:8], objective="Understand the search intent and identify key terms", expected_output="Search parameters"),
                SubTask(id=str(uuid.uuid4())[:8], objective="Execute the search operation", expected_output="Search results"),
                SubTask(id=str(uuid.uuid4())[:8], objective="Verify results match the intent", expected_output="Verification result"),
            ]
        else:
            subtasks = [
                SubTask(id=str(uuid.uuid4())[:8], objective="Analyze the user goal", expected_output="Goal understanding"),
                SubTask(id=str(uuid.uuid4())[:8], objective="Execute the task based on goal", expected_output="Task result"),
                SubTask(id=str(uuid.uuid4())[:8], objective="Verify the result meets the goal", expected_output="Verification result"),
            ]
        
        for i, task in enumerate(subtasks):
            if i > 0:
                subtasks[i].dependencies = [subtasks[i-1].id]
        
        return subtasks

    def _format_subtasks(self, subtasks: list[SubTask]) -> str:
        return "\n".join(f"- {t.id}: {t.objective} (status: {t.status.value}, error: {t.error})" for t in subtasks)

    def _format_errors(self, subtasks: list[SubTask]) -> str:
        errors = []
        for t in subtasks:
            if t.error:
                errors.append(f"  - {t.id}: {t.error}")
        return "\n".join(errors) if errors else "  (no specific errors)"
