"""Memory Manager - coordinates all three layers of memory."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger

from kaolalabot.memory.models import (
    Memory, WorkingMemory, EpisodicMemory, SemanticMemory,
    MemoryLevel, MemoryPriority
)
from kaolalabot.memory.storage import (
    WorkingMemoryStorage, EpisodicMemoryStorage, SemanticMemoryStorage
)


class MemoryManager:
    """
    记忆管理器 - 统一接口
    
    职责:
    1. 协调三层记忆
    2. 记忆检索
    3. 记忆整合
    4. 记忆淘汰
    """
    
    def __init__(
        self,
        workspace: Path,
        working_capacity: int = 20,
        episodic_retention_days: int = 30,
    ):
        self.workspace = workspace
        
        self.working = WorkingMemoryStorage(max_size=working_capacity)
        
        episodic_dir = workspace / "memory" / "episodic"
        self.episodic = EpisodicMemoryStorage(episodic_dir)
        
        semantic_dir = str(workspace / "memory" / "semantic")
        self.semantic = SemanticMemoryStorage(semantic_dir)
        
        self.episodic_retention_days = episodic_retention_days
        
        logger.info(f"Memory manager initialized: workspace={workspace}")
    
    async def add(
        self,
        content: str,
        memory_level: str = "working",
        priority: int = 2,
        **metadata
    ) -> Memory:
        """添加记忆"""
        level = MemoryLevel(memory_level)
        prio = MemoryPriority(priority)
        
        if level == MemoryLevel.WORKING:
            memory = WorkingMemory(
                content=content,
                priority=prio,
                role=metadata.get("role", "user"),
                source_session=metadata.get("session_id"),
            )
            await self.working.save(memory)
            
        elif level == MemoryLevel.EPISODIC:
            expires = datetime.now() + timedelta(days=self.episodic_retention_days)
            memory = EpisodicMemory(
                content=content,
                priority=prio,
                expires_at=expires,
                session_id=metadata.get("session_id", "default"),
                source_session=metadata.get("session_id"),
                tags=metadata.get("tags", []),
            )
            await self.episodic.save(memory)
            
        elif level == MemoryLevel.SEMANTIC:
            memory = SemanticMemory(
                content=content,
                priority=prio,
                title=metadata.get("title", content[:50]),
                summary=metadata.get("summary", content[:200]),
                is_fact=metadata.get("is_fact", False),
                confidence=metadata.get("confidence", 1.0),
                tags=metadata.get("tags", []),
                source_session=metadata.get("session_id"),
            )
            await self.semantic.save(memory)
        
        return memory
    
    async def recall(
        self,
        query: str,
        session_id: Optional[str] = None,
    ) -> list[Memory]:
        """
        检索记忆 - 跨三层搜索
        """
        results = []
        
        working_results = await self.working.search(query, limit=10)
        results.extend(working_results)
        
        episodic_results = await self.episodic.search(
            query, session_id=session_id, limit=10
        )
        results.extend(episodic_results)
        
        semantic_results = await self.semantic.search(query, limit=5)
        results.extend(semantic_results)
        
        return results
    
    async def get_working(self) -> list[WorkingMemory]:
        """获取工作记忆"""
        return await self.working.get_all()
    
    async def get_episodic(self, limit: int = 20, offset: int = 0) -> list[EpisodicMemory]:
        """获取情景记忆"""
        all_memories = list(self.episodic._cache.values())
        all_memories.sort(key=lambda m: m.created_at, reverse=True)
        return all_memories[offset:offset + limit]
    
    async def get_semantic(self, query: str = "", limit: int = 10) -> list[SemanticMemory]:
        """获取语义记忆"""
        if query:
            return await self.semantic.search(query, limit=limit)
        else:
            all_memories = list(self.semantic._cache.values())
            return all_memories[:limit]
    
    async def delete(self, memory_id: str) -> bool:
        """删除记忆"""
        if memory_id in self.working._index:
            return await self.working.delete(memory_id)
        elif memory_id in self.episodic._cache:
            return await self.episodic.delete(memory_id)
        elif memory_id in self.semantic._cache:
            return await self.semantic.delete(memory_id)
        return False
    
    async def promote(self, memory_id: str) -> Optional[SemanticMemory]:
        """提升记忆到语义层"""
        memory = None
        
        if memory_id in self.episodic._cache:
            memory = self.episodic._cache[memory_id]
        elif memory_id in self.working._index:
            idx = self.working._index[memory_id]
            if idx < len(self.working._memories):
                memory = self.working._memories[idx]
        
        if memory:
            semantic = SemanticMemory(
                content=memory.content,
                title=memory.content[:50],
                summary=memory.content[:200],
                is_fact=self._is_fact(memory.content),
                tags=memory.tags,
                priority=MemoryPriority.HIGH,
                source_session=memory.source_session,
            )
            await self.semantic.save(semantic)
            return semantic
        
        return None
    
    async def consolidate(self) -> None:
        """记忆整合"""
        recent = await self.episodic.get_recent(days=7, limit=100)
        
        for memory in recent:
            importance = self._calculate_importance(memory)
            
            if importance > 0.7:
                semantic = SemanticMemory(
                    content=memory.content,
                    title=self._extract_title(memory.content),
                    summary=memory.content[:200],
                    is_fact=self._is_fact(memory.content),
                    priority=MemoryPriority.HIGH,
                    tags=memory.tags,
                    source_session=memory.source_session,
                )
                await self.semantic.save(semantic)
                logger.info(f"Consolidated memory {memory.id} to semantic")
        
        await self._cleanup_expired()
    
    async def _cleanup_expired(self) -> None:
        """清理过期记忆"""
        now = datetime.now()
        
        for memory_id in list(self.episodic._cache.keys()):
            memory = self.episodic._cache[memory_id]
            if memory.expires_at and memory.expires_at < now:
                await self.episodic.delete(memory_id)
                logger.info(f"Deleted expired memory {memory_id}")
    
    async def clear_working(self) -> None:
        """清空工作记忆"""
        await self.working.clear()
        logger.info("Working memory cleared")
    
    def _calculate_importance(self, memory: Memory) -> float:
        """计算记忆重要性"""
        score = 0.5
        
        score += min(memory.access_count * 0.05, 0.3)
        
        score += (memory.priority.value - 2) * 0.1
        
        important_keywords = ["记住", "重要", "偏好", "不要忘记", "关键", "remember", "important"]
        for kw in important_keywords:
            if kw.lower() in memory.content.lower():
                score += 0.1
        
        return min(max(score, 0.0), 1.0)
    
    def _extract_title(self, content: str) -> str:
        """提取标题"""
        return content[:50] + ("..." if len(content) > 50 else "")
    
    def _is_fact(self, content: str) -> bool:
        """判断是否是事实"""
        fact_indicators = ["是", "位于", "等于", "叫做", "称为", "is", "located", "equals", "called"]
        return any(ind in content for ind in fact_indicators)
