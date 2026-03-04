"""Procedural memory extraction from task logs."""

import re
from datetime import datetime
from typing import Optional

from loguru import logger

from kaolalabot.memory.models import (
    MemoryItem, MemoryType, ProceduralInfo, TaskLog
)


class ProcedureExtractor:
    """
    程序记忆提炼引擎
    
    从任务日志中抽取技能模板:
    - 前置条件
    - 推荐步骤
    - 关键观察点
    - 常见失败模式
    - 恢复方案
    - 不适用条件
    """
    
    def __init__(self):
        self._failure_patterns = self._init_failure_patterns()
        self._success_indicators = self._init_success_indicators()
        
        logger.info("ProcedureExtractor initialized")
    
    def _init_failure_patterns(self) -> list[tuple[str, str]]:
        return [
            (r"(?:error|failed|失败|错误)(?:\s*:|\s*-)(\s*.+)", "general_error"),
            (r"(?:timeout|超时)", "timeout"),
            (r"(?:permission denied|权限不足)", "permission_error"),
            (r"(?:not found|不存在|找不到)", "not_found"),
            (r"(?:connection refused|连接失败)", "connection_error"),
            (r"(?:invalid|无效|格式错误)", "validation_error"),
            (r"(?:null|None|undefined|空值)", "null_pointer"),
        ]
    
    def _init_success_indicators(self) -> list[str]:
        return [
            "success", "completed", "done", "successfully",
            "成功", "完成", "已创建", "已更新", "已删除"
        ]
    
    async def extract(
        self,
        task_log: TaskLog,
    ) -> Optional[MemoryItem]:
        """
        从任务日志中提取程序记忆
        
        Args:
            task_log: 任务执行日志
            
        Returns:
            程序记忆项 (如果可提取)
        """
        if not task_log.steps and not task_log.tool_calls:
            logger.debug(f"Task {task_log.task_id} has no steps to extract")
            return None
        
        action_steps = self._extract_action_steps(task_log)
        
        if not action_steps:
            return None
        
        preconditions = self._extract_preconditions(task_log)
        
        observables = self._extract_observables(task_log)
        
        failure_modes = self._extract_failure_modes(task_log)
        
        recovery_plan = self._extract_recovery_plan(task_log)
        
        tool_dependencies = self._extract_tool_dependencies(task_log)
        
        success_rate = 1.0 if task_log.success else 0.0
        
        content = self._build_procedural_content(
            task_log.task_type,
            action_steps,
            preconditions,
            failure_modes,
        )
        
        procedural_info = ProceduralInfo(
            preconditions=preconditions,
            action_steps=action_steps,
            observables=observables,
            failure_modes=failure_modes,
            recovery_plan=recovery_plan,
            tool_dependencies=tool_dependencies,
            success_rate=success_rate,
        )
        
        memory = MemoryItem(
            type=MemoryType.PROCEDURAL,
            content_raw=content,
            summary=f"处理{task_log.task_type}任务的技能模板",
            procedural=procedural_info,
        )
        
        logger.info(f"Extracted procedural memory for task type: {task_log.task_type}")
        return memory
    
    def _extract_action_steps(self, task_log: TaskLog) -> list[str]:
        """提取操作步骤"""
        steps = []
        
        for step in task_log.steps:
            if isinstance(step, dict):
                description = step.get("description") or step.get("action") or step.get("name", "")
            else:
                description = str(step)
            
            if description:
                steps.append(description)
        
        for tool_call in task_log.tool_calls:
            if isinstance(tool_call, dict):
                tool_name = tool_call.get("tool", tool_call.get("name", ""))
                args = tool_call.get("args", {})
                description = f"调用 {tool_name}"
                if args:
                    description += f" 参数: {args}"
                steps.append(description)
        
        return steps
    
    def _extract_preconditions(self, task_log: TaskLog) -> list[str]:
        """提取前置条件"""
        preconditions = [task_log.task_type]
        
        tool_patterns = {
            "code": ["代码文件存在", "代码语法正确"],
            "file": ["文件路径有效"],
            "network": ["网络连接正常"],
            "database": ["数据库连接正常"],
        }
        
        for tool_call in task_log.tool_calls:
            if isinstance(tool_call, dict):
                tool_name = str(tool_call.get("tool", "")).lower()
                for key, preqs in tool_patterns.items():
                    if key in tool_name:
                        preconditions.extend(preqs)
        
        return list(set(preconditions))
    
    def _extract_observables(self, task_log: TaskLog) -> list[str]:
        """提取可观察点"""
        observables = []
        
        for obs in task_log.observations:
            if obs:
                observables.append(obs)
        
        for step in task_log.steps:
            if isinstance(step, dict):
                expected = step.get("expected") or step.get("result")
                if expected:
                    observables.append(f"期望: {expected}")
        
        return observables[:5]
    
    def _extract_failure_modes(self, task_log: TaskLog) -> list[str]:
        """提取失败模式"""
        failure_modes = []
        
        if task_log.error:
            error_lower = task_log.error.lower()
            
            for pattern, failure_type in self._failure_patterns:
                if re.search(pattern, error_lower, re.IGNORECASE):
                    failure_modes.append(failure_type)
                    break
            else:
                failure_modes.append("unknown_error")
        
        for recovery in task_log.recovery_actions:
            if recovery:
                failure_modes.append(f"recovered_by: {recovery}")
        
        return list(set(failure_modes))
    
    def _extract_recovery_plan(self, task_log: TaskLog) -> list[str]:
        """提取恢复方案"""
        recovery_plan = []
        
        recovery_plan.extend(task_log.recovery_actions)
        
        if not task_log.success:
            generic_recoveries = [
                "检查错误日志",
                "验证输入参数",
                "重试操作",
                "回滚到之前状态",
            ]
            recovery_plan.extend(generic_recoveries)
        
        return list(set(recovery_plan))[:5]
    
    def _extract_tool_dependencies(self, task_log: TaskLog) -> list[str]:
        """提取工具依赖"""
        tools = []
        
        for tool_call in task_log.tool_calls:
            if isinstance(tool_call, dict):
                tool_name = tool_call.get("tool") or tool_call.get("name")
                if tool_name:
                    tools.append(tool_name)
        
        return list(set(tools))
    
    def _build_procedural_content(
        self,
        task_type: str,
        action_steps: list[str],
        preconditions: list[str],
        failure_modes: list[str],
    ) -> str:
        """构建程序记忆内容"""
        lines = [
            f"任务类型: {task_type}",
            "",
            "前置条件:",
        ]
        
        for preq in preconditions[:3]:
            lines.append(f"  - {preq}")
        
        lines.extend([
            "",
            "操作步骤:",
        ])
        
        for i, step in enumerate(action_steps[:5], 1):
            lines.append(f"  {i}. {step}")
        
        if failure_modes:
            lines.extend([
                "",
                "常见失败模式:",
            ])
            for mode in failure_modes[:3]:
                lines.append(f"  - {mode}")
        
        return "\n".join(lines)


class ProcedureUpdater:
    """
    程序记忆更新器
    
    根据任务执行结果更新程序记忆:
    - 多次成功后提高优先级
    - 多次失败后降低权重或标记失效
    """
    
    def __init__(self):
        logger.info("ProcedureUpdater initialized")
    
    async def update(
        self,
        procedure: MemoryItem,
        task_log: TaskLog,
    ) -> MemoryItem:
        """
        更新程序记忆
        
        Args:
            procedure: 程序记忆
            task_log: 任务日志
            
        Returns:
            更新后的程序记忆
        """
        if procedure.type != MemoryType.PROCEDURAL or not procedure.procedural:
            logger.warning(f"Memory {procedure.id} is not a procedural memory")
            return procedure
        
        if task_log.success:
            await self._handle_success(procedure, task_log)
        else:
            await self._handle_failure(procedure, task_log)
        
        logger.info(f"Updated procedural memory {procedure.id}: success_rate={procedure.procedural.success_rate:.2f}")
        return procedure
    
    async def _handle_success(
        self,
        procedure: MemoryItem,
        task_log: TaskLog,
    ) -> None:
        """处理成功执行"""
        procedure.meta.success_reuse_count += 1
        
        total_attempts = procedure.meta.success_reuse_count + procedure.meta.failure_reuse_count
        procedure.procedural.success_rate = procedure.meta.success_reuse_count / max(1, total_attempts)
        
        procedure.meta.confidence = min(procedure.meta.confidence + 0.05, 1.0)
        
        if procedure.meta.salience < 0.8:
            procedure.meta.salience = min(procedure.meta.salience + 0.1, 1.0)
        
        new_step = task_log.steps[-1] if task_log.steps else None
        if new_step and len(procedure.procedural.action_steps) < 10:
            if isinstance(new_step, dict):
                desc = new_step.get("description", str(new_step))
            else:
                desc = str(new_step)
            
            if desc and desc not in procedure.procedural.action_steps:
                procedure.procedural.action_steps.append(desc)
        
        logger.debug(f"Procedural memory {procedure.id} reinforced after success")
    
    async def _handle_failure(
        self,
        procedure: MemoryItem,
        task_log: TaskLog,
    ) -> None:
        """处理失败执行"""
        procedure.meta.failure_reuse_count += 1
        
        total_attempts = procedure.meta.success_reuse_count + procedure.meta.failure_reuse_count
        procedure.procedural.success_rate = procedure.meta.success_reuse_count / max(1, total_attempts)
        
        if task_log.error:
            error_category = self._categorize_error(task_log.error)
            if error_category not in procedure.procedural.failure_modes:
                procedure.procedural.failure_modes.append(error_category)
        
        procedure.recovery_actions = task_log.recovery_actions
        if task_log.recovery_actions:
            procedure.procedural.recovery_plan.extend(task_log.recovery_actions)
            procedure.procedural.recovery_plan = list(set(procedure.procedural.recovery_plan))[:10]
        
        if procedure.procedural.success_rate < 0.3:
            procedure.meta.salience = max(procedure.meta.salience - 0.2, 0.1)
            procedure.meta.confidence = max(procedure.meta.confidence - 0.15, 0.1)
        
        logger.warning(f"Procedural memory {procedure.id} weakened after failure: rate={procedure.procedural.success_rate:.2f}")
    
    def _categorize_error(self, error: str) -> str:
        """错误分类"""
        error_lower = error.lower()
        
        error_categories = [
            ("timeout", ["timeout", "超时"]),
            ("permission", ["permission", "权限", "denied"]),
            ("not_found", ["not found", "不存在", "找不到"]),
            ("connection", ["connection", "连接"]),
            ("validation", ["invalid", "无效", "格式"]),
        ]
        
        for category, keywords in error_categories:
            for kw in keywords:
                if kw in error_lower:
                    return category
        
        return "unknown_error"
