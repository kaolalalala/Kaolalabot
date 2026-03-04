"""Chain of Thought (CoT) Engine

Implementation of multi-step reasoning with observation, analysis, action, and reflection phases.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator, Optional

from loguru import logger


class ThinkPhase(Enum):
    """思维阶段"""
    OBSERVE = "observe"       # 观察理解
    REASON = "reason"         # 推理分析
    ACT = "act"              # 行动执行
    REFLECT = "reflect"      # 反思总结


@dataclass
class ThinkStep:
    """思维步骤"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    phase: ThinkPhase = ThinkPhase.OBSERVE
    content: str = ""
    reasoning: str = ""
    confidence: float = 1.0
    tool_used: Optional[str] = None
    result: Optional[str] = None
    parent_id: Optional[str] = None
    children_ids: list[str] = field(default_factory=list)
    status: str = "pending"


@dataclass
class ThinkChain:
    """思维链"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    steps: dict[str, ThinkStep] = field(default_factory=dict)
    root_id: Optional[str] = None
    current_id: Optional[str] = None
    created_at: float = field(default_factory=lambda: __import__("time").time())
    
    def add_step(self, step: ThinkStep, parent_id: Optional[str] = None) -> None:
        """添加思维步骤"""
        step.parent_id = parent_id
        self.steps[step.id] = step
        
        if parent_id and parent_id in self.steps:
            self.steps[parent_id].children_ids.append(step.id)
        
        if self.root_id is None:
            self.root_id = step.id
        
        self.current_id = step.id
    
    def get_step(self, step_id: str) -> Optional[ThinkStep]:
        """获取步骤"""
        return self.steps.get(step_id)
    
    def get_current_step(self) -> Optional[ThinkStep]:
        """获取当前步骤"""
        if self.current_id:
            return self.steps.get(self.current_id)
        return None
    
    def to_list(self) -> list[dict]:
        """转换为列表"""
        result = []
        for step in self.steps.values():
            result.append({
                "id": step.id,
                "phase": step.phase.value,
                "content": step.content,
                "reasoning": step.reasoning,
                "confidence": step.confidence,
                "tool_used": step.tool_used,
                "result": step.result,
                "parent_id": step.parent_id,
                "children_ids": step.children_ids,
                "status": step.status,
            })
        return result


class CoTEngine:
    """
    Chain of Thought 思维链引擎
    
    工作流程:
    1. OBSERVE - 理解用户输入
    2. REASON - 逐步推理
    3. ACT - 执行行动(工具调用)
    4. REFLECT - 反思总结
    """
    
    def __init__(
        self,
        llm_provider,
        tools,
        max_iterations: int = 10,
        enable_reflection: bool = True,
    ):
        self.llm = llm_provider
        self.tools = tools
        self.max_iterations = max_iterations
        self.enable_reflection = enable_reflection
    
    async def think(
        self,
        user_input: str,
        context: list[dict],
        session_id: str,
    ) -> AsyncGenerator[ThinkStep, None]:
        """
        执行思维链
        
        Yields:
            ThinkStep: 思维步骤
        """
        chain = ThinkChain(session_id=session_id)
        
        observe_step = await self._observe(user_input, context)
        chain.add_step(observe_step)
        yield observe_step
        
        reason_step = await self._reason(user_input, context, observe_step)
        chain.add_step(reason_step, observe_step.id)
        yield reason_step
        
        act_step = await self._act(user_input, context, reason_step)
        chain.add_step(act_step, reason_step.id)
        yield act_step
        
        if self.enable_reflection:
            reflect_step = await self._reflect(user_input, context, chain)
            chain.add_step(reflect_step, act_step.id)
            yield reflect_step
    
    async def _observe(self, user_input: str, context: list[dict]) -> ThinkStep:
        """观察阶段 - 理解用户输入"""
        prompt = f"""你是一个AI助手。请分析以下用户输入:

用户输入: {user_input}

请用一句话描述:
1. 用户想要什么?
2. 需要什么信息?
3. 可能需要什么工具?

注意: 直接给出分析结果，不要有其他格式。"""
        
        try:
            response = await self.llm.chat([
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input}
            ])
            
            return ThinkStep(
                phase=ThinkPhase.OBSERVE,
                content=response.content if response.content else user_input,
                reasoning="理解用户意图和需求",
                confidence=0.9
            )
        except Exception as e:
            logger.warning(f"Observe step failed: {e}")
            return ThinkStep(
                phase=ThinkPhase.OBSERVE,
                content=user_input,
                reasoning="理解用户意图和需求",
                confidence=0.5
            )
    
    async def _reason(
        self, 
        user_input: str, 
        context: list[dict],
        observe_step: ThinkStep
    ) -> ThinkStep:
        """推理阶段 - 分析问题"""
        
        prompt = f"""用户输入: {user_input}

上一步理解: {observe_step.content}

请进行推理，分析如何解决这个问题。
列出具体的推理步骤。"""
        
        try:
            response = await self.llm.chat([
                {"role": "system", "content": prompt},
                *context,
                {"role": "user", "content": "请进行推理分析"}
            ])
            
            content = response.content if response.content else "完成推理分析"
            
            return ThinkStep(
                phase=ThinkPhase.REASON,
                content=content,
                reasoning="推理分析问题",
                confidence=0.85
            )
        except Exception as e:
            logger.warning(f"Reason step failed: {e}")
            return ThinkStep(
                phase=ThinkPhase.REASON,
                content="完成推理分析",
                reasoning="推理分析问题",
                confidence=0.5
            )
    
    async def _act(
        self,
        user_input: str,
        context: list[dict],
        reason_step: ThinkStep
    ) -> ThinkStep:
        """行动阶段 - 生成回答或执行工具"""
        
        prompt = f"""基于以下推理:

{reason_step.content}

用户输入: {user_input}

请生成一个完整、有帮助的回答。"""
        
        try:
            response = await self.llm.chat([
                {"role": "system", "content": prompt},
                *context,
                {"role": "user", "content": user_input}
            ])
            
            return ThinkStep(
                phase=ThinkPhase.ACT,
                content=response.content if response.content else "生成回答",
                reasoning="生成最终回答",
                tool_used=None,
                confidence=0.8
            )
        except Exception as e:
            logger.warning(f"Act step failed: {e}")
            return ThinkStep(
                phase=ThinkPhase.ACT,
                content="生成回答",
                reasoning="生成最终回答",
                confidence=0.5
            )
    
    async def _reflect(
        self,
        user_input: str,
        context: list[dict],
        chain: ThinkChain
    ) -> ThinkStep:
        """反思阶段 - 审视结果"""
        
        steps_summary = "\n".join([
            f"- {step.phase.value}: {step.content[:100]}"
            for step in chain.steps.values()
        ])
        
        prompt = f"""请反思以下思考过程:

{steps_summary}

用户输入: {user_input}

这个结果是否正确?有什么可以改进的?
请简短总结。"""
        
        try:
            response = await self.llm.chat([
                {"role": "system", "content": prompt},
                *context
            ])
            
            return ThinkStep(
                phase=ThinkPhase.REFLECT,
                content=response.content if response.content else "反思完成",
                reasoning="反思整个思考过程",
                confidence=0.75
            )
        except Exception as e:
            logger.warning(f"Reflect step failed: {e}")
            return ThinkStep(
                phase=ThinkPhase.REFLECT,
                content="反思完成",
                reasoning="反思整个思考过程",
                confidence=0.5
            )
    
    async def generate_response(
        self,
        user_input: str,
        context: list[dict],
    ) -> str:
        """生成最终回答"""
        
        prompt = f"""你是一个有用的AI助手。

用户消息: {user_input}

请直接给出回答，不需要额外说明思考过程。"""
        
        try:
            response = await self.llm.chat([
                {"role": "system", "content": prompt},
                *context,
                {"role": "user", "content": user_input}
            ])
            
            return response.content or "抱歉，我无法生成回答。"
        except Exception as e:
            logger.error(f"Generate response failed: {e}")
            return f"生成回答时出错: {str(e)[:100]}"
