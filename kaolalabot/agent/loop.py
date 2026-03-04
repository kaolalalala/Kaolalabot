"""Agent loop: the core processing engine."""

from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import quote_plus, urlparse
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from loguru import logger

from kaolalabot.agent.context import ContextBuilder
from kaolalabot.agent.native_commands import NativeCommandPlan, NativeCommandRouter
from kaolalabot.agent.tools.registry import ToolRegistry
from kaolalabot.agent.tools.parallel import ParallelToolExecutor
from kaolalabot.agent.intent_classifier import IntentClassifier, AdaptiveIntentClassifier
from kaolalabot.bus.events import InboundMessage, OutboundMessage
from kaolalabot.bus.queue import MessageBus
from kaolalabot.bus.rate_limit import MultiDimensionalRateLimiter, RateLimitConfig
from kaolalabot.providers.base import LLMProvider
from kaolalabot.session.manager import Session, SessionManager
from kaolalabot.session.state_tracker import SessionStateTracker, ContextType

if TYPE_CHECKING:
    from kaolalabot.config.schema import ChannelsConfig, ExecToolConfig


class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives messages from the bus
    2. Builds context with history
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """

    _TOOL_RESULT_MAX_CHARS = 500

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 40,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        memory_window: int = 100,
        reasoning_effort: str | None = None,
        exec_config: ExecToolConfig | None = None,
        session_manager: SessionManager | None = None,
        channels_config: ChannelsConfig | None = None,
        tool_registry: ToolRegistry | None = None,
        tools_config: "ToolsConfig | None" = None,
        rate_limit_config: "RateLimitConfig | None" = None,
    ):
        from kaolalabot.config.schema import ExecToolConfig, ToolsConfig, RateLimitConfig
        self.bus = bus
        self.channels_config = channels_config
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.memory_window = memory_window
        self.reasoning_effort = reasoning_effort
        self.exec_config = exec_config or ExecToolConfig()
        self.tools_config = tools_config or ToolsConfig()
        self.rate_limit_config = rate_limit_config or RateLimitConfig()
        self._react_mode_enabled = bool(getattr(self.tools_config, "react_mode_enabled", True))
        self._react_observation_enabled = bool(getattr(self.tools_config, "react_observation_enabled", True))

        self.context = ContextBuilder(workspace)
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = tool_registry if tool_registry else ToolRegistry()

        self._rate_limiter = MultiDimensionalRateLimiter(
            config=RateLimitConfig(
                requests_per_minute=self.rate_limit_config.requests_per_minute,
                requests_per_hour=self.rate_limit_config.requests_per_hour,
                burst_size=self.rate_limit_config.burst_size,
                enabled=self.rate_limit_config.enabled,
            )
        )

        self._parallel_executor = ParallelToolExecutor(
            max_workers=self.tools_config.max_parallel_workers,
            timeout=self.tools_config.tool_timeout,
            enable_parallel=self.tools_config.parallel_execution,
        )

        self._session_state_tracker = SessionStateTracker()

        self._intent_classifier = AdaptiveIntentClassifier(
            confidence_threshold=0.7,
        )
        self._native_router = NativeCommandRouter()

        self._running = False
        self._active_tasks: dict[str, list[asyncio.Task]] = {}
        self._session_locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def _strip_think(text: str | None) -> str | None:
        """Remove <think blocks from content."""
        if not text:
            return None
        return re.sub(r"<llll[\s\S]*?>>>>", "", text).strip() or None

    @staticmethod
    def _tool_hint(tool_calls: list) -> str:
        """Format tool calls as concise hint."""
        names: list[str] = []
        for tc in tool_calls:
            if tc.name not in names:
                names.append(tc.name)
        return ", ".join(names)

    @staticmethod
    def _sanitize_feishu_content(text: str | None) -> str:
        """Sanitize model output for Feishu user-facing messages."""
        if not text:
            return ""

        cleaned = re.sub(r"```[\s\S]*?```", "", text)
        filtered_lines: list[str] = []

        for raw_line in cleaned.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            lower = line.lower()
            if any(
                token in lower
                for token in (
                    "chat_id",
                    "chat id",
                    "message_id",
                    "session_key",
                    "runtime context",
                    "metadata only",
                    "not instructions",
                    "current time",
                    "intent:",
                    "intent：",
                )
            ):
                continue
            if any(token in line for token in ("聊天ID", "当前时间", "意图：", "意图:", "飞书频道")):
                continue
            if re.match(r"^\s*(import\s+\w+|from\s+\S+\s+import\s+.+)\s*$", line):
                continue
            if re.match(r"^\s*(def |class |if |for |while |try:|except|with |return |print\()", line):
                continue
            if re.match(r"^\s*[A-Za-z_]\w*\s*=", line):
                continue
            if line.startswith("#"):
                continue

            filtered_lines.append(line)

        cleaned = "\n".join(filtered_lines).strip()
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned

    @staticmethod
    def _clean_tool_result(text: str) -> str:
        """Strip internal retry hints from tool output."""
        if not text:
            return ""
        cleaned = re.sub(r"\n?\[Analyze the error above and try a different approach\.\]\s*$", "", text.strip())
        return cleaned.strip()

    def _verify_tool_observation(self, tool_name: str, tool_result: str) -> tuple[bool, str]:
        """Heuristic observation verification for ReAct action results."""
        cleaned = self._clean_tool_result(tool_result)
        if not cleaned:
            return False, "empty tool result"

        lower = cleaned.lower()
        if lower.startswith("error"):
            return False, cleaned[:200]
        if any(token in lower for token in ("failed", "permission denied", "not found")):
            return False, cleaned[:200]

        if cleaned.startswith("{") or cleaned.startswith("["):
            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    if parsed.get("ok") is False:
                        return False, str(parsed.get("error") or parsed)[:200]
                    if parsed.get("ok") is True:
                        return True, "json response ok=true"
                    if parsed.get("success") is False:
                        return False, str(parsed.get("error") or parsed)[:200]
                    if parsed.get("success") is True:
                        return True, "json response success=true"
            except Exception:
                pass

        if tool_name == "exec" and "application launch command executed" in lower:
            return True, "application launch acknowledged"
        return True, "tool returned non-error output"

    def _annotate_tool_result_with_observation(self, tool_name: str, tool_result: str) -> str:
        """Attach observation verification summary to tool result for next reasoning step."""
        cleaned = self._clean_tool_result(tool_result)
        if not self._react_observation_enabled:
            return cleaned
        ok, note = self._verify_tool_observation(tool_name, cleaned)
        status = "success" if ok else "failed"
        observation = (
            f"[Observation]\n"
            f"tool: {tool_name}\n"
            f"status: {status}\n"
            f"note: {note}"
        )
        return f"{cleaned}\n\n{observation}" if cleaned else observation

    @staticmethod
    def _snapshot_to_text(snapshot: str) -> str:
        """Normalize OpenClaw snapshot output into searchable plain text."""
        if not snapshot:
            return ""

        raw = snapshot.strip()
        if not raw:
            return ""

        if not (raw.startswith("{") or raw.startswith("[")):
            return raw

        def _collect(value: Any, out: list[str]) -> None:
            if isinstance(value, str):
                text = value.strip()
                if text:
                    out.append(text)
                return
            if isinstance(value, dict):
                for key in ("snapshot", "text", "markdown", "content", "title", "url", "ref"):
                    if key in value:
                        _collect(value.get(key), out)
                for v in value.values():
                    _collect(v, out)
                return
            if isinstance(value, list):
                for item in value:
                    _collect(item, out)

        try:
            parsed = json.loads(raw)
        except Exception:
            return raw

        pieces: list[str] = []
        _collect(parsed, pieces)
        return "\n".join(pieces) if pieces else raw

    @staticmethod
    def _extract_ref_from_snapshot(snapshot: str, preferred_terms: list[str] | None = None) -> str | None:
        """Extract best candidate element ref from OpenClaw snapshot text."""
        if not snapshot:
            return None

        terms = [t.lower() for t in (preferred_terms or []) if t and t.strip()]
        lines = AgentLoop._snapshot_to_text(snapshot).splitlines()
        ref_patterns = [
            re.compile(r"ref\s*=\s*([a-z]?\d+)", re.IGNORECASE),
            re.compile(r"\[ref\s*=\s*([a-z]?\d+)\]", re.IGNORECASE),
            re.compile(r"\b([a-z]\d+)\b", re.IGNORECASE),
        ]

        def _find_ref(line: str) -> str | None:
            for pat in ref_patterns:
                m = pat.search(line)
                if m:
                    return m.group(1)
            return None

        # Rank refs instead of returning first hit, to avoid clicking wrong elements.
        candidates: list[tuple[int, str]] = []
        for line in lines:
            ref = _find_ref(line)
            if not ref:
                continue
            lower = line.lower()
            score = 0
            if terms and any(term in lower for term in terms):
                score += 10
            if any(token in lower for token in ("search", "textbox", "input", "query", "查找", "搜索")):
                score += 6
            if any(token in lower for token in ("skip", "sign in", "登录", "注册", "menu", "导航")):
                score -= 4
            candidates.append((score, ref))

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            # Require a positive confidence score when preferred terms are provided.
            if not terms or candidates[0][0] > 0:
                return candidates[0][1]

        if terms:
            for line in lines:
                lower = line.lower()
                if any(term in lower for term in terms):
                    ref = _find_ref(line)
                    if ref:
                        return ref

        for line in lines:
            ref = _find_ref(line)
            if ref:
                return ref
        return None

    def _build_native_result_message(self, plan: NativeCommandPlan, tool_result: str) -> str:
        """Build a concise end-user report for deterministic native command execution."""
        cleaned = self._clean_tool_result(tool_result)
        if cleaned.startswith("Error"):
            return f"{plan.summary} failed: {cleaned}"

        if plan.kind == "launch_app":
            return f"Executed: {plan.summary}."
        if plan.kind == "browser_automation":
            if len(cleaned) > 1200:
                cleaned = cleaned[:1200] + "\n... (truncated)"
            return f"{plan.summary} completed. Result:\n{cleaned}"

        if not cleaned:
            return f"{plan.summary} completed."

        if len(cleaned) > 1600:
            cleaned = cleaned[:1600] + "\n... (truncated)"
        return f"{plan.summary} completed. Result:\n{cleaned}"

    async def _try_native_command(
        self,
        msg: InboundMessage,
        session: Session,
        session_key: str,
    ) -> OutboundMessage | None:
        """Execute deterministic local commands without relying on model tool-calls."""
        if not self.tools_config.native_commands_enabled:
            return None

        plan = self._native_router.plan(msg.content)
        if not plan:
            return None

        logger.info("Using native command router for {}: {}", msg.channel, plan.summary)
        if plan.kind == "browser_automation" and plan.tool_name and plan.tool_args is not None:
            tool_result = await self._run_browser_automation_plan(plan)
        else:
            tool_result = await self.tools.execute("exec", {"command": plan.command})
        logger.info("Native command executed: {} => {}", plan.command, self._clean_tool_result(tool_result)[:200])
        response_text = self._build_native_result_message(plan, tool_result)

        if msg.channel == "feishu":
            response_text = self._sanitize_feishu_content(response_text)
            if not response_text:
                response_text = "任务已执行完成。"

        session.add_message("user", msg.content)
        session.add_message("assistant", response_text)
        self.sessions.save(session)

        metadata = dict(msg.metadata or {}) if msg.metadata else {}
        metadata["session_id"] = session_key
        metadata["native_command"] = True
        metadata["native_summary"] = plan.summary

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=response_text,
            metadata=metadata,
        )

    async def _run_browser_automation_plan(self, plan: NativeCommandPlan) -> str:
        """Run browser automation with OpenClaw browser priority and Playwright fallback."""
        workflow = (plan.tool_args or {}).get("workflow", {})
        if self.tools.has("kaola_browser") and isinstance(workflow, dict) and workflow:
            result = await self._run_ref_browser_workflow("kaola_browser", workflow)
            if not result.startswith("Error"):
                return result
            logger.warning("Kaola browser workflow failed, fallback to next backend: {}", result[:200])
        if self.tools.has("openclaw_browser") and isinstance(workflow, dict) and workflow:
            result = await self._run_ref_browser_workflow("openclaw_browser", workflow)
            if not result.startswith("Error"):
                return result
            logger.warning("OpenClaw browser workflow failed, fallback to playwright: {}", result[:200])

        if plan.tool_name and plan.tool_args is not None:
            args = dict(plan.tool_args)
            if plan.tool_name == "playwright" and "script" in args and isinstance(args["script"], dict):
                # Playwright tool does not accept workflow metadata directly.
                args = {"script": args["script"]}
            return await self.tools.execute(plan.tool_name, args)
        return "Error: browser automation plan is missing tool data"

    async def _run_ref_browser_workflow(self, tool_name: str, workflow: dict[str, Any]) -> str:
        """Execute deterministic browser workflow through a ref-capable browser tool."""
        outer_query = str(workflow.get("outer_query") or "").strip()
        inner_query = str(workflow.get("inner_query") or "").strip()
        target_url = str(workflow.get("target_url") or "").strip()

        steps: list[dict[str, Any]] = []

        async def _call(**params: Any) -> str:
            out = await self.tools.execute(tool_name, params)
            steps.append({"params": params, "result": self._clean_tool_result(out)[:500]})
            return out

        r = await _call(action="start")
        if r.startswith("Error"):
            return r

        if target_url:
            r = await _call(action="open", target_url=target_url)
            if r.startswith("Error"):
                return r
        else:
            q = quote_plus(outer_query or "github")
            r = await _call(action="open", target_url=f"https://www.google.com/search?q={q}")
            if r.startswith("Error"):
                return r

        if target_url:
            domain = urlparse(target_url).netloc.lower()
            snapshot = await _call(action="snapshot", interactive=True, compact=True, limit=240)
            if not snapshot.startswith("Error"):
                input_ref = self._extract_ref_from_snapshot(
                    snapshot,
                    preferred_terms=["search or jump", "search", "query", "搜索", "查找"],
                )
                if input_ref:
                    r = await _call(
                        action="act",
                        request={"kind": "type", "ref": input_ref, "text": inner_query, "submit": True},
                    )
                    if not r.startswith("Error"):
                        # Observe whether the page has moved into a result view; otherwise fallback.
                        post_snapshot = await _call(action="snapshot", interactive=True, compact=True, limit=260)
                        normalized = self._snapshot_to_text(post_snapshot).lower()
                        if any(t in normalized for t in ("no results", "nothing to show", "not found")):
                            r = "Error: OpenClaw act produced no search results"
                    if r.startswith("Error"):
                        if "github.com" in domain:
                            q = quote_plus(inner_query)
                            search_url = f"https://github.com/search?q={q}&type=repositories"
                        else:
                            q = quote_plus(f"site:{domain} {inner_query}")
                            search_url = f"https://www.google.com/search?q={q}"
                        r = await _call(action="navigate", target_url=search_url)
                        if r.startswith("Error"):
                            return r
                else:
                    if "github.com" in domain:
                        q = quote_plus(inner_query)
                        search_url = f"https://github.com/search?q={q}&type=repositories"
                    else:
                        q = quote_plus(f"site:{domain} {inner_query}")
                        search_url = f"https://www.google.com/search?q={q}"
                    r = await _call(action="navigate", target_url=search_url)
                    if r.startswith("Error"):
                        return r
            else:
                if "github.com" in domain:
                    q = quote_plus(inner_query)
                    search_url = f"https://github.com/search?q={q}&type=repositories"
                else:
                    q = quote_plus(f"site:{domain} {inner_query}")
                    search_url = f"https://www.google.com/search?q={q}"
                r = await _call(action="navigate", target_url=search_url)
                if r.startswith("Error"):
                    return r
        else:
            search_snapshot = await _call(action="snapshot", interactive=True, compact=True, limit=260)
            first_result_ref = None
            if not search_snapshot.startswith("Error"):
                first_result_ref = self._extract_ref_from_snapshot(
                    search_snapshot,
                    preferred_terms=[outer_query, "github", "result", "结果"],
                )
            if first_result_ref:
                r = await _call(action="act", request={"kind": "click", "ref": first_result_ref})
                if r.startswith("Error"):
                    return r

        snap = await _call(action="snapshot", interactive=True, limit=200)
        status = "ok" if not snap.startswith("Error") else "degraded"
        return json.dumps(
            {
                "ok": status == "ok",
                "status": status,
                "tool": tool_name,
                "workflow": {
                    "outer_query": outer_query,
                    "inner_query": inner_query,
                    "target_url": target_url,
                },
                "steps": steps,
            },
            ensure_ascii=False,
        )

    async def _run_openclaw_browser_workflow(self, workflow: dict[str, Any]) -> str:
        """Backward-compatible alias for existing tests/callers."""
        return await self._run_ref_browser_workflow("openclaw_browser", workflow)

    async def _run_agent_loop(
        self,
        initial_messages: list[dict],
        on_progress: Callable[..., Awaitable[None]] | None = None,
    ) -> tuple[str | None, list[str], list[dict]]:
        """Run the agent iteration loop. Returns (final_content, tools_used, messages)."""
        messages = initial_messages
        iteration = 0
        final_content = None
        tools_used: list[str] = []

        while iteration < self.max_iterations:
            iteration += 1

            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                reasoning_effort=self.reasoning_effort,
            )

            if response.has_tool_calls:
                if on_progress:
                    clean = self._strip_think(response.content)
                    if clean:
                        await on_progress(clean)
                    await on_progress(self._tool_hint(response.tool_calls), tool_hint=True)

                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )

                if len(response.tool_calls) > 1 and self._parallel_executor.is_parallel_enabled:
                    tool_calls_input = [
                        (tc.id, tc.name, tc.arguments)
                        for tc in response.tool_calls
                    ]
                    logger.info(f"Executing {len(tool_calls_input)} tools in parallel")
                    results = await self._parallel_executor.execute_parallel(
                        tool_calls_input,
                        self.tools.execute,
                    )
                    tool_results_dict = {tool_id: result for tool_id, result in results}
                    for tool_call in response.tool_calls:
                        tools_used.append(tool_call.name)
                        args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                        logger.info("Tool call: {}({})", tool_call.name, args_str[:200])
                        raw_result = tool_results_dict.get(tool_call.id, "Error: No result")
                        result = (
                            self._annotate_tool_result_with_observation(tool_call.name, raw_result)
                            if self._react_mode_enabled
                            else raw_result
                        )
                        messages = self.context.add_tool_result(
                            messages, tool_call.id, tool_call.name, result
                        )
                else:
                    for tool_call in response.tool_calls:
                        tools_used.append(tool_call.name)
                        args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                        logger.info("Tool call: {}({})", tool_call.name, args_str[:200])
                        raw_result = await self.tools.execute(tool_call.name, tool_call.arguments)
                        result = (
                            self._annotate_tool_result_with_observation(tool_call.name, raw_result)
                            if self._react_mode_enabled
                            else raw_result
                        )
                        messages = self.context.add_tool_result(
                            messages, tool_call.id, tool_call.name, result
                        )
            else:
                clean = self._strip_think(response.content)
                if response.finish_reason == "error":
                    logger.error("LLM returned error: {}", (clean or "")[:200])
                    final_content = clean or "Sorry, I encountered an error calling the AI model."
                    break
                messages = self.context.add_assistant_message(
                    messages, clean, reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )
                final_content = clean
                break

        if final_content is None and iteration >= self.max_iterations:
            logger.warning("Max iterations ({}) reached", self.max_iterations)
            final_content = (
                f"I reached the maximum number of tool call iterations ({self.max_iterations}) "
                "without completing the task. You can try breaking the task into smaller steps."
            )

        return final_content, tools_used, messages

    async def run(self) -> None:
        """Run the agent loop, dispatching messages as tasks."""
        self._running = True
        logger.info("Agent loop started")

        while self._running:
            try:
                msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            task = asyncio.create_task(self._dispatch(msg))
            self._active_tasks.setdefault(msg.session_key, []).append(task)
            task.add_done_callback(
                lambda t, k=msg.session_key: self._active_tasks.get(k, []) and 
                self._active_tasks[k].remove(t) if t in self._active_tasks.get(k, []) else None
            )

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")

    async def _dispatch(self, msg: InboundMessage) -> None:
        """Process a message under a per-session lock."""
        is_allowed, limit_info = await self._rate_limiter.check_rate_limit(
            user_id=msg.sender_id,
            channel=msg.channel,
        )
        
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for {msg.sender_id}: {limit_info}")
            await self.bus.publish_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id,
                content=f"鐠囬攱鐪版潻鍥︾艾妫版垹绠掗敍宀冾嚞缁嬪秴鎮楅崘宥堢槸閵嗗倿妾洪崚? {limit_info.get('violations', [])}",
            ))
            return
        
        lock = self._session_locks.setdefault(msg.session_key, asyncio.Lock())
        async with lock:
            try:
                response = await self._process_message(msg)
                if response is not None:
                    await self.bus.publish_outbound(response)
                elif msg.channel == "cli":
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id,
                        content="", metadata=msg.metadata or {},
                    ))
            except asyncio.CancelledError:
                logger.info("Task cancelled for session {}", msg.session_key)
                raise
            except Exception:
                logger.exception("Error processing message for session {}", msg.session_key)
                await self.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id,
                    content="Sorry, I encountered an error.",
                ))

    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> OutboundMessage | None:
        """Process a single inbound message and return the response."""
        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info("Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview)

        key = session_key or msg.session_key
        session = self.sessions.get_or_create(key)

        self._session_state_tracker.update_activity(key)
        self._session_state_tracker.record_message(key, "user", msg.content)

        intent_context = {
            "turn_count": self._session_state_tracker.get_or_create_session(key).turn_count,
            "last_intent": None,
        }
        intent_result = self._intent_classifier.classify(
            msg.content,
            context=intent_context,
        )
        
        self._session_state_tracker.add_context(
            key,
            ContextType.INTENT,
            f"{intent_result.primary_intent.category.value}:{intent_result.primary_intent.confidence:.2f}",
            importance=intent_result.primary_intent.confidence,
        )

        cmd = msg.content.strip().lower()
        if cmd == "/new":
            session.clear()
            self.sessions.save(session)
            self.sessions.invalidate(session.key)
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content="New session started.")
        if cmd == "/help":
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="Kaolalabot commands:\n/new - Start a new conversation\n/help - Show available commands",
            )

        native_response = await self._try_native_command(msg, session, key)
        if native_response is not None:
            return native_response

        history = session.get_history(max_messages=self.memory_window)
        initial_messages = self.context.build_messages(
            history=history,
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel, chat_id=msg.chat_id,
        )

        async def _bus_progress(content: str, *, tool_hint: bool = False) -> None:
            meta = dict(msg.metadata or {})
            meta["_progress"] = True
            meta["_tool_hint"] = tool_hint

            progress_content = content
            if msg.channel == "feishu":
                # Feishu should only receive concise execution-status progress.
                if not tool_hint:
                    return
                hint = (content or "").strip()
                progress_content = f"正在执行任务: {hint}" if hint else "正在执行任务..."

            await self.bus.publish_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=progress_content, metadata=meta,
            ))

        final_content, _, all_msgs = await self._run_agent_loop(
            initial_messages, on_progress=on_progress or _bus_progress,
        )

        if final_content is None:
            final_content = "I've completed processing but have no response to give."
        elif msg.channel == "feishu":
            final_content = self._sanitize_feishu_content(final_content)
            if not final_content:
                final_content = "任务已执行完成。"

        self._save_turn(session, all_msgs, 1 + len(history))
        self.sessions.save(session)

        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info("Response to {}:{}: {}", msg.channel, msg.sender_id, preview)
        
        metadata = dict(msg.metadata or {}) if msg.metadata else {}
        metadata["session_id"] = key
        
        return OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content=final_content,
            metadata=metadata,
        )

    def _save_turn(self, session: Session, messages: list[dict], skip: int) -> None:
        """Save new-turn messages into session."""
        from datetime import datetime
        for m in messages[skip:]:
            entry = dict(m)
            role, content = entry.get("role"), entry.get("content")
            if role == "assistant" and not content and not entry.get("tool_calls"):
                continue
            if role == "tool" and isinstance(content, str) and len(content) > self._TOOL_RESULT_MAX_CHARS:
                entry["content"] = content[:self._TOOL_RESULT_MAX_CHARS] + "\n... (truncated)"
            elif role == "user":
                if isinstance(content, str) and content.startswith(ContextBuilder._RUNTIME_CONTEXT_TAG):
                    continue
                if isinstance(content, list):
                    entry["content"] = [
                        {"type": "text", "text": "[image]"} if (
                            c.get("type") == "image_url"
                            and c.get("image_url", {}).get("url", "").startswith("data:image/")
                        ) else c for c in content
                    ]
            entry.setdefault("timestamp", datetime.now().isoformat())
            session.messages.append(entry)
        session.updated_at = datetime.now()

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """Process a message directly (for CLI usage)."""
        msg = InboundMessage(channel=channel, sender_id="user", chat_id=chat_id, content=content)
        response = await self._process_message(msg, session_key=session_key, on_progress=on_progress)
        return response.content if response else ""

