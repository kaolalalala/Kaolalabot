"""Memory decay, consolidation, and reconsolidation."""

from datetime import datetime, timedelta
from typing import Optional

from loguru import logger

from kaolalabot.memory.models import (
    MemoryItem, MemoryType, ProceduralInfo
)


class DecayAndArchive:
    """
    遗忘与归档机制
    
    遗忘策略:
    1. 激活衰减 - 长期不使用，优先级下降
    2. 归档压缩 - 低频低价值内容转为摘要
    3. 硬删除 - 明确错误、已过期、隐私要求删除
    """
    
    DEFAULT_DECAY_RATE = 0.95
    DEFAULT_ARCHIVE_THRESHOLD = 0.3
    DEFAULT_HARD_DELETE_DAYS = 90
    
    def __init__(
        self,
        decay_rate: float = DEFAULT_DECAY_RATE,
        archive_threshold: float = DEFAULT_ARCHIVE_THRESHOLD,
        hard_delete_days: int = DEFAULT_HARD_DELETE_DAYS,
    ):
        self.decay_rate = decay_rate
        self.archive_threshold = archive_threshold
        self.hard_delete_days = hard_delete_days
        
        logger.info(f"DecayAndArchive initialized: decay_rate={decay_rate}, archive_threshold={archive_threshold}")
    
    async def apply_decay(self, memory: MemoryItem) -> MemoryItem:
        """
        应用激活衰减
        
        长期未访问的记忆，其显著性(salience)会逐渐下降
        """
        days_since_access = (datetime.now() - memory.meta.access_count).total_seconds() / 86400
        
        if days_since_access < 1:
            return memory
        
        decay_factor = self.decay_rate ** min(days_since_access, 30)
        
        memory.meta.salience *= decay_factor
        
        if memory.type == MemoryType.PROCEDURAL and memory.procedural:
            if memory.procedural.success_rate > 0:
                memory.procedural.success_rate *= (0.99 ** min(days_since_access, 30))
        
        return memory
    
    async def should_archive(self, memory: MemoryItem) -> bool:
        """
        判断是否应该归档
        
        条件:
        1. 长时间未访问
        2. 低访问频率
        3. 低显著性
        """
        if memory.meta.archived:
            return False
        
        days_since_access = (datetime.now() - memory.last_accessed_at).days
        
        if days_since_access < 30:
            return False
        
        access_frequency = memory.meta.access_count / max(1, days_since_access)
        
        priority_score = (
            memory.meta.salience * 0.5 +
            min(access_frequency * 10, 0.3) +
            (1.0 if memory.type in [MemoryType.SEMANTIC, MemoryType.PROCEDURAL] else 0.2)
        )
        
        if priority_score < self.archive_threshold:
            logger.info(f"Memory {memory.id} marked for archiving: priority_score={priority_score:.3f}")
            return True
        
        return False
    
    async def archive_memory(self, memory: MemoryItem) -> MemoryItem:
        """归档记忆"""
        memory.meta.archived = True
        
        if not memory.summary and len(memory.content_raw) > 200:
            memory.summary = memory.content_raw[:200] + "..."
        
        logger.info(f"Archived memory {memory.id}")
        return memory
    
    async def should_hard_delete(self, memory: MemoryItem) -> bool:
        """
        判断是否应该硬删除
        
        条件:
        1. 明确错误
        2. 已过期
        3. 隐私要求
        4. 归档后长期未访问
        """
        if memory.meta.invalid_at and memory.meta.invalid_at < datetime.now():
            return True
        
        if memory.meta.privacy_level.value >= 2:
            days_since_access = (datetime.now() - memory.last_accessed_at).days
            if days_since_access > self.hard_delete_days:
                return True
        
        if memory.meta.conflict_ids:
            days_since_creation = (datetime.now() - memory.created_at).days
            if days_since_creation > self.hard_delete_days:
                return True
        
        return False


class ConsolidationEngine:
    """
    记忆巩固引擎
    
    负责记忆在不同层之间的迁移:
    - Sensory -> Working
    - Working -> Episodic
    - 多个 Episodic -> Semantic
    - 多次成功的 Episodic -> Procedural
    """
    
    def __init__(
        self,
        episodic_to_semantic_threshold: int = 3,
        episodic_to_procedural_threshold: int = 5,
    ):
        self.episodic_to_semantic_threshold = episodic_to_semantic_threshold
        self.episodic_to_procedural_threshold = episodic_to_procedural_threshold
        
        logger.info(f"ConsolidationEngine initialized: e2s={episodic_to_semantic_threshold}, e2p={episodic_to_procedural_threshold}")
    
    async def consolidate_working_to_episodic(
        self,
        working_memories: list[MemoryItem],
        session_id: str,
    ) -> list[MemoryItem]:
        """将工作记忆巩固为情景记忆"""
        episodic_memories = []
        
        for wm in working_memories:
            if wm.type != MemoryType.WORKING:
                continue
            
            if wm.meta.salience < 0.3:
                continue
            
            episodic = MemoryItem(
                type=MemoryType.EPISODIC,
                content_raw=wm.content_raw,
                summary=wm.summary,
                entities=wm.entities,
                relations=wm.relations,
                session_id=session_id,
                meta=wm.meta,
            )
            
            episodic_memories.append(episodic)
            logger.debug(f"Consolidated working memory {wm.id} to episodic")
        
        return episodic_memories
    
    async def consolidate_episodic_to_semantic(
        self,
        episodic_memories: list[MemoryItem],
    ) -> Optional[MemoryItem]:
        """
        将多个情景记忆巩固为语义记忆
        
        当多个相似的情景记忆被访问多次时，提炼出通用模式
        """
        if len(episodic_memories) < self.episodic_to_semantic_threshold:
            return None
        
        content_similarity = self._calculate_similarity(episodic_memories)
        
        if content_similarity < 0.5:
            return None
        
        avg_confidence = sum(m.meta.confidence for m in episodic_memories) / len(episodic_memories)
        
        all_entities = []
        for m in episodic_memories:
            all_entities.extend(m.entities)
        
        combined_content = "; ".join(m.content_raw for m in episodic_memories[:3])
        
        semantic = MemoryItem(
            type=MemoryType.SEMANTIC,
            content_raw=combined_content,
            summary=self._generate_summary(combined_content),
            entities=list(set(all_entities)),
            meta=episodic_memories[0].meta,
        )
        semantic.meta.confidence = min(avg_confidence + 0.1, 1.0)
        
        logger.info(f"Consolidated {len(episodic_memories)} episodic memories to semantic")
        return semantic
    
    async def consolidate_episodic_to_procedural(
        self,
        episodic_memories: list[MemoryItem],
        task_type: str,
    ) -> Optional[MemoryItem]:
        """
        将成功的经验巩固为程序记忆
        
        当某类任务多次成功执行后，生成可复用的技能模板
        """
        successful = [m for m in episodic_memories if m.meta.success_reuse_count > 0]
        
        if len(successful) < self.episodic_to_procedural_threshold:
            return None
        
        procedural_info = ProceduralInfo(
            preconditions=[task_type],
            action_steps=[m.content_raw for m in successful[:5]],
            success_rate=sum(m.meta.success_reuse_count for m in successful) / len(successful),
        )
        
        combined_content = f"任务类型: {task_type}\n" + "\n".join(
            f"步骤{i+1}: {m.content_raw}" for i, m in enumerate(successful[:3])
        )
        
        procedural = MemoryItem(
            type=MemoryType.PROCEDURAL,
            content_raw=combined_content,
            summary=f"处理{task_type}任务的技能模板",
            procedural=procedural_info,
            meta=successful[0].meta,
        )
        procedural.meta.confidence = 0.8
        
        logger.info(f"Consolidated {len(successful)} successful experiences to procedural")
        return procedural
    
    def _calculate_similarity(self, memories: list[MemoryItem]) -> float:
        """计算记忆间的相似度"""
        if len(memories) < 2:
            return 0.0
        
        similarities = []
        for i in range(len(memories)):
            for j in range(i + 1, len(memories)):
                sim = self._text_similarity(
                    memories[i].content_raw,
                    memories[j].content_raw
                )
                similarities.append(sim)
        
        return sum(similarities) / len(similarities) if similarities else 0.0
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """简单的文本相似度计算"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def _generate_summary(self, content: str) -> str:
        """生成摘要"""
        if len(content) <= 200:
            return content
        
        return content[:200] + "..."


class ReconsolidationEngine:
    """
    记忆重整合引擎
    
    当记忆被使用后，根据使用结果更新记忆:
    - 成功: 提高权重、增加成功复用次数
    - 失败: 降低置信度、记录失败原因
    - 重复: 合并相似记忆
    - 冲突: 建立冲突链
    - 成熟: 把事件抽象成语义或技能模板
    """
    
    def __init__(self):
        logger.info("ReconsolidationEngine initialized")
    
    async def reconsolidate(
        self,
        memory: MemoryItem,
        outcome: bool,
        context: Optional[dict] = None,
    ) -> MemoryItem:
        """
        重整合记忆
        
        Args:
            memory: 被使用的记忆
            outcome: 使用结果 (True=成功, False=失败)
            context: 额外的上下文信息
            
        Returns:
            更新后的记忆
        """
        context = context or {}
        
        memory.last_verified_at = datetime.now()
        
        if outcome:
            memory.meta.success_reuse_count += 1
            
            memory.meta.confidence = min(memory.meta.confidence + 0.05, 1.0)
            
            memory.meta.salience = min(memory.meta.salience + 0.1, 1.0)
            
            if memory.type == MemoryType.PROCEDURAL and memory.procedural:
                total = memory.meta.success_reuse_count + memory.meta.failure_reuse_count
                if total > 0:
                    memory.procedural.success_rate = memory.meta.success_reuse_count / total
            
            logger.info(f"Memory {memory.id} reinforced: success_count={memory.meta.success_reuse_count}")
        else:
            memory.meta.failure_reuse_count += 1
            
            memory.meta.confidence = max(memory.meta.confidence - 0.1, 0.1)
            
            failure_reason = context.get("failure_reason")
            if failure_reason:
                memory.meta.conflict_ids.append(f"failure_{datetime.now().timestamp()}")
            
            if memory.type == MemoryType.PROCEDURAL and memory.procedural:
                memory.procedural.failure_modes.append(failure_reason or "unknown")
                
                total = memory.meta.success_reuse_count + memory.meta.failure_reuse_count
                if total > 0:
                    memory.procedural.success_rate = memory.meta.success_reuse_count / total
                
                if memory.procedural.success_rate < 0.3:
                    memory.meta.salience = max(memory.meta.salience - 0.2, 0.1)
            
            logger.warning(f"Memory {memory.id} weakened: failure_count={memory.meta.failure_reuse_count}")
        
        return memory
    
    async def resolve_conflict(
        self,
        memory1: MemoryItem,
        memory2: MemoryItem,
        resolution: str = "newer",
    ) -> tuple[MemoryItem, MemoryItem]:
        """
        解决记忆冲突
        
        Args:
            memory1: 记忆1
            memory2: 记忆2
            resolution: 解决策略 (newer/older/merge)
            
        Returns:
            解决后的两个记忆
        """
        memory1.meta.conflict_ids.append(memory2.id)
        memory2.meta.conflict_ids.append(memory1.id)
        
        if resolution == "newer":
            if memory1.created_at < memory2.created_at:
                memory1.meta.confidence = max(memory1.meta.confidence - 0.2, 0.1)
                memory2.meta.confidence = min(memory2.meta.confidence + 0.1, 1.0)
            else:
                memory2.meta.confidence = max(memory2.meta.confidence - 0.2, 0.1)
                memory1.meta.confidence = min(memory1.meta.confidence + 0.1, 1.0)
        
        elif resolution == "merge":
            merged_content = f"{memory1.content_raw}\n---\n{memory2.content_raw}"
            memory1.content_raw = merged_content
            memory2.meta.invalid_at = datetime.now()
            memory2.meta.confidence = 0.0
        
        logger.info(f"Resolved conflict between {memory1.id} and {memory2.id} using {resolution}")
        
        return memory1, memory2
    
    async def merge_similar(
        self,
        memory1: MemoryItem,
        memory2: MemoryItem,
    ) -> MemoryItem:
        """
        合并相似记忆
        
        保留较新、置信度较高的版本，合并内容
        """
        if memory1.created_at < memory2.created_at:
            primary, secondary = memory2, memory1
        else:
            primary, secondary = memory1, memory2
        
        primary.content_raw = f"{primary.content_raw}\n{secondary.content_raw}"
        
        if len(primary.summary) < 200:
            primary.summary = f"{primary.summary} {secondary.summary}"[:200]
        
        primary.entities = list(set(primary.entities + secondary.entities))
        
        primary.meta.confidence = (primary.meta.confidence + secondary.meta.confidence) / 2
        
        secondary.meta.invalid_at = datetime.now()
        
        logger.info(f"Merged memory {secondary.id} into {primary.id}")
        
        return primary
