"""Memory Manager V2 - Unified interface for layered memory system."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger

from kaolalabot.memory.models import (
    MemoryItem, MemoryType, InputCategory, ContentSource,
    IngestionCandidate, TaskLog, RetrievalResult
)
from kaolalabot.memory.gate import IngestionGate, SensoryBufferManager
from kaolalabot.memory.retrieval import RetrievalEngine
from kaolalabot.memory.consolidation import (
    DecayAndArchive, ConsolidationEngine, ReconsolidationEngine
)
from kaolalabot.memory.procedures import ProcedureExtractor, ProcedureUpdater


class MemoryManagerV2:
    """
    记忆管理器V2 - 分层记忆系统统一接口
    
    职责:
    1. 协调六层记忆 (Sensory/Working/Episodic/Semantic/Procedural/Meta)
    2. 记忆摄入与路由
    3. 记忆检索 (三阶段)
    4. 记忆整合与巩固
    5. 记忆遗忘与归档
    6. 记忆重整合
    7. 程序记忆提炼
    """
    
    def __init__(
        self,
        workspace: Path,
        config: Optional[dict] = None,
    ):
        self.workspace = workspace
        self.config = config or {}
        
        memory_dir = workspace / "memory" / "v2"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.gate = IngestionGate()
        
        self.sensory = SensoryBufferManager(
            max_size=self.config.get("sensory_max_size", 50),
            ttl_seconds=self.config.get("sensory_ttl", 300),
        )
        
        self.retrieval = RetrievalEngine(memory_dir)
        
        self.decay = DecayAndArchive(
            decay_rate=self.config.get("decay_rate", 0.95),
            archive_threshold=self.config.get("archive_threshold", 0.3),
            hard_delete_days=self.config.get("hard_delete_days", 90),
        )
        
        self.consolidation = ConsolidationEngine(
            episodic_to_semantic_threshold=self.config.get("e2s_threshold", 3),
            episodic_to_procedural_threshold=self.config.get("e2p_threshold", 5),
        )
        
        self.reconsolidation = ReconsolidationEngine()
        
        self.procedure_extractor = ProcedureExtractor()
        self.procedure_updater = ProcedureUpdater()
        
        self._working_cache: dict[str, list[MemoryItem]] = {}
        
        self._background_tasks: list[asyncio.Task] = []
        
        logger.info(f"MemoryManagerV2 initialized: workspace={workspace}")
    
    async def ingest(
        self,
        content: str,
        source: ContentSource = ContentSource.USER_INPUT,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Optional[MemoryItem]:
        """
        摄入新记忆
        
        接口: ingest(input) -> candidates
        """
        self.sensory.add(content, source)
        
        candidate = self.gate.classify(content, source)
        
        should_store, reason = self.gate.should_store(candidate)
        
        if not should_store:
            logger.debug(f"Content rejected by gate: reason={reason}")
            return None
        
        memory = self.gate.create_memory_item(candidate, session_id)
        memory.task_id = task_id
        
        await self._store_memory(memory)
        
        logger.info(f"Ingested memory: type={memory.type.value}, id={memory.id[:8]}")
        return memory
    
    async def store(self, memory: MemoryItem) -> None:
        """
        直接存储记忆
        
        接口: store(memories)
        """
        await self._store_memory(memory)
    
    async def _store_memory(self, memory: MemoryItem) -> None:
        """内部存储逻辑"""
        await self.retrieval.add_memory(memory)
        
        if memory.type == MemoryType.WORKING:
            session_id = memory.session_id or "default"
            if session_id not in self._working_cache:
                self._working_cache[session_id] = []
            
            self._working_cache[session_id].append(memory)
            
            max_working = self.config.get("working_max_size", 20)
            if len(self._working_cache[session_id]) > max_working:
                old = self._working_cache[session_id].pop(0)
                episodic = MemoryItem(
                    type=MemoryType.EPISODIC,
                    content_raw=old.content_raw,
                    summary=old.summary,
                    session_id=session_id,
                    meta=old.meta,
                )
                await self.retrieval.add_memory(episodic)
    
    async def retrieve(
        self,
        query: str,
        context: Optional[dict] = None,
        budget: int = 20,
    ) -> list[RetrievalResult]:
        """
        检索记忆
        
        接口: retrieve(query, context) -> ranked_memories
        """
        return await self.retrieval.retrieve(query, context, budget)
    
    async def apply_memory(
        self,
        memories: list[RetrievalResult],
        task_context: dict,
    ) -> str:
        """
        将记忆应用于任务上下文
        
        接口: apply_memory(memories, task_context) -> usable_context
        """
        if not memories:
            return ""
        
        usable_parts = []
        
        for result in memories[:5]:
            mem = result.memory
            
            if mem.type == MemoryType.PROCEDURAL and mem.procedural:
                usable_parts.append(f"[技能模板] {mem.summary}")
                if mem.procedural.action_steps:
                    usable_parts.append("步骤: " + "; ".join(mem.procedural.action_steps[:3]))
            
            elif mem.type == MemoryType.SEMANTIC:
                usable_parts.append(f"[知识] {mem.summary or mem.content_raw[:200]}")
            
            elif mem.type == MemoryType.EPISODIC:
                usable_parts.append(f"[经验] {mem.content_raw[:200]}")
            
            if result.ambiguities:
                usable_parts.append(f"[注意] 可能存在: {', '.join(result.ambiguities)}")
        
        if task_context.get("include_alternatives"):
            for result in memories[5:10]:
                if result.alternatives:
                    usable_parts.append(f"[备选] {result.memory.id[:8]}")
        
        return "\n\n".join(usable_parts)
    
    async def reconsolidate(
        self,
        memory_ids: list[str],
        outcome: bool,
        context: Optional[dict] = None,
    ) -> list[MemoryItem]:
        """
        重整合记忆
        
        接口: reconsolidate(memory_ids, outcome)
        """
        updated = []
        
        all_memories = self.retrieval.get_all()
        memory_map = {m.id: m for m in all_memories}
        
        for mem_id in memory_ids:
            if mem_id in memory_map:
                memory = memory_map[mem_id]
                updated_memory = await self.reconsolidation.reconsolidate(memory, outcome, context)
                await self.retrieval.update_memory(updated_memory)
                updated.append(updated_memory)
        
        return updated
    
    async def decay_and_archive(self) -> None:
        """
        执行遗忘与归档
        
        接口: decay_and_archive()
        """
        all_memories = self.retrieval.get_all()
        
        archived_count = 0
        deleted_count = 0
        
        for memory in all_memories:
            if memory.meta.archived:
                continue
            
            await self.decay.apply_decay(memory)
            
            if await self.decay.should_archive(memory):
                await self.decay.archive_memory(memory)
                await self.retrieval.update_memory(memory)
                archived_count += 1
            
            elif await self.decay.should_hard_delete(memory):
                await self.retrieval.delete_memory(memory.id)
                deleted_count += 1
        
        logger.info(f"Decay/Archive completed: archived={archived_count}, deleted={deleted_count}")
    
    async def extract_procedure(
        self,
        task_log: dict,
    ) -> Optional[MemoryItem]:
        """
        从任务日志提炼程序记忆
        
        接口: extract_procedure(task_log) -> procedure_memory
        """
        log = TaskLog.from_dict(task_log) if isinstance(task_log, dict) else task_log
        
        procedure = await self.procedure_extractor.extract(log)
        
        if procedure:
            await self._store_memory(procedure)
            logger.info(f"Extracted procedure: {procedure.id[:8]}")
        
        return procedure
    
    async def update_procedure(
        self,
        procedure_id: str,
        task_log: dict,
    ) -> Optional[MemoryItem]:
        """更新程序记忆"""
        all_memories = self.retrieval.get_all()
        
        procedure = None
        for m in all_memories:
            if m.id == procedure_id:
                procedure = m
                break
        
        if not procedure:
            return None
        
        log = TaskLog.from_dict(task_log) if isinstance(task_log, dict) else task_log
        
        updated = await self.procedure_updater.update(procedure, log)
        await self.retrieval.update_memory(updated)
        
        return updated
    
    async def get_working(self, session_id: Optional[str] = None) -> list[MemoryItem]:
        """获取工作记忆"""
        if session_id:
            return self._working_cache.get(session_id, [])
        else:
            all_working = []
            for memories in self._working_cache.values():
                all_working.extend(memories)
            return all_working
    
    async def get_by_type(
        self,
        memory_type: MemoryType,
        limit: int = 50,
    ) -> list[MemoryItem]:
        """按类型获取记忆"""
        all_memories = self.retrieval.get_all()
        filtered = [m for m in all_memories if m.type == memory_type]
        
        if memory_type == MemoryType.SEMANTIC:
            filtered.sort(key=lambda m: m.meta.confidence, reverse=True)
        elif memory_type == MemoryType.PROCEDURAL:
            filtered.sort(key=lambda m: m.procedural.success_rate if m.procedural else 0, reverse=True)
        else:
            filtered.sort(key=lambda m: m.created_at, reverse=True)
        
        return filtered[:limit]
    
    async def consolidate(self) -> None:
        """执行记忆巩固"""
        working_memories = await self.get_working()
        
        for session_id in self._working_cache:
            session_working = self._working_cache.get(session_id, [])
            
            episodic = await self.consolidation.consolidate_working_to_episodic(
                session_working, session_id
            )
            for e in episodic:
                await self._store_memory(e)
        
        episodic_memories = await self.get_by_type(MemoryType.EPISODIC, limit=100)
        
        if len(episodic_memories) >= 3:
            semantic = await self.consolidation.consolidate_episodic_to_semantic(episodic_memories)
            if semantic:
                await self._store_memory(semantic)
        
        logger.info("Consolidation completed")
    
    async def delete(self, memory_id: str) -> bool:
        """删除记忆"""
        return await self.retrieval.delete_memory(memory_id)
    
    async def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str = "temporal",
    ) -> None:
        """添加记忆关联"""
        await self.retrieval.add_relation(source_id, target_id, relation_type)
    
    async def clear_working(self, session_id: Optional[str] = None) -> None:
        """清空工作记忆"""
        if session_id:
            self._working_cache.pop(session_id, None)
        else:
            self._working_cache.clear()
        
        logger.info(f"Working memory cleared: session={session_id}")
    
    def get_stats(self) -> dict:
        """获取记忆统计"""
        all_memories = self.retrieval.get_all()
        
        stats = {
            "total": len(all_memories),
            "by_type": {},
            "archived": sum(1 for m in all_memories if m.meta.archived),
            "conflicts": sum(1 for m in all_memories if m.meta.conflict_ids),
        }
        
        for mem_type in MemoryType:
            count = sum(1 for m in all_memories if m.type == mem_type)
            stats["by_type"][mem_type.value] = count
        
        if self._working_cache:
            stats["working_sessions"] = len(self._working_cache)
        
        return stats
