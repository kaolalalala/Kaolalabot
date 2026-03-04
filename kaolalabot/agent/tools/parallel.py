"""Parallel tool execution with thread pool and async task queue."""

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class ToolTask:
    """A tool execution task."""
    id: str
    name: str
    arguments: dict[str, Any]
    future: asyncio.Future = field(default_factory=asyncio.Future)
    start_time: float = 0.0


class ParallelToolExecutor:
    """
    Parallel tool execution with thread pool and async task queue.
    
    Implements concurrent tool execution to reduce overall tool call time.
    Supports both async and sync tools with configurable parallelism.
    """

    def __init__(
        self,
        max_workers: int = 4,
        timeout: float = 60.0,
        enable_parallel: bool = True,
    ):
        self.max_workers = max_workers
        self.timeout = timeout
        self.enable_parallel = enable_parallel
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="tool_exec")
        self._running_tasks: dict[str, ToolTask] = {}
        self._semaphore = asyncio.Semaphore(max_workers)

    async def execute_parallel(
        self,
        tool_calls: list[tuple[str, dict[str, Any], str]],
        executor_func: Callable[[str, dict[str, Any]], Any],
    ) -> list[tuple[str, str]]:
        """
        Execute multiple tool calls in parallel.

        Args:
            tool_calls: List of (tool_id, tool_name, arguments) tuples
            executor_func: Async function to execute each tool

        Returns:
            List of (tool_id, result) tuples in original order
        """
        if not tool_calls or not self.enable_parallel:
            return await self._execute_sequential(tool_calls, executor_func)

        logger.info(f"Executing {len(tool_calls)} tools in parallel (max_workers={self.max_workers})")

        tasks = []
        for tool_id, tool_name, arguments in tool_calls:
            task = asyncio.create_task(
                self._execute_with_semaphore(tool_id, tool_name, arguments, executor_func)
            )
            tasks.append((tool_id, task))

        results = []
        for tool_id, task in tasks:
            try:
                result = await asyncio.wait_for(task, timeout=self.timeout)
                results.append((tool_id, result))
            except asyncio.TimeoutError:
                logger.error(f"Tool execution timeout: {tool_id}")
                results.append((tool_id, f"Error: Tool execution timed out after {self.timeout}s"))
            except Exception as e:
                logger.error(f"Tool execution error for {tool_id}: {e}")
                results.append((tool_id, f"Error: {str(e)}"))

        return results

    async def _execute_with_semaphore(
        self,
        tool_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        executor_func: Callable[[str, dict[str, Any]], Any],
    ) -> str:
        """Execute a single tool with semaphore control."""
        async with self._semaphore:
            try:
                return await asyncio.wait_for(
                    executor_func(tool_name, arguments),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                return f"Error: Tool '{tool_name}' execution timed out"
            except Exception as e:
                return f"Error executing {tool_name}: {str(e)}"

    async def _execute_sequential(
        self,
        tool_calls: list[tuple[str, dict[str, Any], str]],
        executor_func: Callable[[str, dict[str, Any]], Any],
    ) -> list[tuple[str, str]]:
        """Execute tools sequentially as fallback."""
        results = []
        for tool_id, tool_name, arguments in tool_calls:
            try:
                result = await asyncio.wait_for(
                    executor_func(tool_name, arguments),
                    timeout=self.timeout
                )
                results.append((tool_id, result))
            except asyncio.TimeoutError:
                results.append((tool_id, f"Error: Tool execution timed out"))
            except Exception as e:
                results.append((tool_id, f"Error: {str(e)}"))
        return results

    async def execute_single(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        executor_func: Callable[[str, dict[str, Any]], Any],
    ) -> str:
        """Execute a single tool call."""
        async with self._semaphore:
            try:
                return await asyncio.wait_for(
                    executor_func(tool_name, arguments),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                return f"Error: Tool '{tool_name}' execution timed out"
            except Exception as e:
                return f"Error executing {tool_name}: {str(e)}"

    def shutdown(self) -> None:
        """Shutdown the thread pool executor."""
        self._executor.shutdown(wait=True)
        logger.info("Parallel tool executor shut down")

    @property
    def is_parallel_enabled(self) -> bool:
        """Check if parallel execution is enabled."""
        return self.enable_parallel


class ToolCallBatcher:
    """
    Batches independent tool calls for parallel execution.
    
    Analyzes tool call dependencies and groups them for optimal
    parallel execution.
    """

    def __init__(self, max_batch_size: int = 10):
        self.max_batch_size = max_batch_size

    def analyze_dependencies(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> list[list[int]]:
        """
        Analyze dependencies between tool calls.
        
        Returns list of batches where each batch can be executed in parallel.
        Currently assumes all tools are independent.
        """
        if not tool_calls:
            return []

        batches = []
        for i in range(0, len(tool_calls), self.max_batch_size):
            batch = list(range(i, min(i + self.max_batch_size, len(tool_calls))))
            batches.append(batch)
        return batches

    def group_independent_calls(
        self,
        tool_calls: list[tuple[str, dict[str, Any]]],
    ) -> list[list[tuple[str, dict[str, Any]]]]:
        """
        Group tool calls that can be executed in parallel.
        
        Currently groups all calls together. Can be extended to analyze
        dependencies based on tool arguments.
        """
        if not tool_calls:
            return []

        batches = []
        for i in range(0, len(tool_calls), self.max_batch_size):
            batch = tool_calls[i:i + self.max_batch_size]
            batches.append(batch)
        return batches
