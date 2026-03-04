"""Three-stage retrieval system for memory."""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np

from loguru import logger

from kaolalabot.memory.models import (
    MemoryItem, MemoryType, RetrievalResult, ContentSource
)


class EmbeddingGenerator:
    """轻量级embedding生成器"""
    
    _EMBED_DIM = 128
    
    _TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
    
    def __init__(self):
        try:
            import xxhash
            self._xxhash = xxhash
        except ImportError:
            self._xxhash = None
    
    def generate(self, text: str) -> list[float]:
        if not text:
            return [0.0] * self._EMBED_DIM
        
        vec = np.zeros(self._EMBED_DIM, dtype=np.float32)
        tokens = self._TOKEN_RE.findall(text.lower())
        
        if not tokens:
            return vec.tolist()
        
        for token in tokens:
            if self._xxhash:
                idx = self._xxhash.xxh32(token.encode("utf-8")).intdigest() % self._EMBED_DIM
            else:
                idx = hash(token) % self._EMBED_DIM
            vec[idx] += 1.0
        
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()
    
    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        a = np.array(a)
        b = np.array(b)
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))


class RetrievalEngine:
    """
    三阶段检索引擎
    
    阶段1: 候选召回
    阶段2: 局部关联扩展
    阶段3: 重排
    """
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self._cache: dict[str, MemoryItem] = {}
        self._embedding_gen = EmbeddingGenerator()
        
        self._relation_graph: dict[str, list[dict]] = {}
        
        self._load_from_disk()
        
        logger.info(f"RetrievalEngine initialized: {len(self._cache)} items cached")
    
    async def retrieve(
        self,
        query: str,
        context: Optional[dict] = None,
        budget: int = 20,
    ) -> list[RetrievalResult]:
        """
        执行三阶段检索
        
        Args:
            query: 查询文本
            context: 任务上下文
            budget: token预算
            
        Returns:
            排序后的检索结果
        """
        context = context or {}
        
        stage1_candidates = await self._stage1_recall(query, context, limit=budget * 2)
        
        logger.debug(f"Stage1: {len(stage1_candidates)} candidates recalled")
        
        if not stage1_candidates:
            return []
        
        stage2_expanded = await self._stage2_expand(
            stage1_candidates, 
            context,
            max_hops=2,
            max_nodes_per_hop=5
        )
        
        logger.debug(f"Stage2: {len(stage2_expanded)} nodes after expansion")
        
        stage3_ranked = await self._stage3_rerank(
            stage2_expanded,
            query,
            context
        )
        
        results = stage3_ranked[:budget]
        
        for result in results:
            result.memory.meta.access_count += 1
            result.memory.last_accessed_at = datetime.now()
        
        logger.info(f"Retrieved {len(results)} memories for query: {query[:50]}...")
        return results
    
    async def _stage1_recall(
        self,
        query: str,
        context: dict,
        limit: int = 40,
    ) -> list[MemoryItem]:
        """阶段1: 候选召回"""
        candidates = []
        
        query_embedding = self._embedding_gen.generate(query)
        
        type_filter = context.get("memory_types")
        if type_filter is None:
            type_filter = [MemoryType.WORKING, MemoryType.EPISODIC, MemoryType.SEMANTIC, MemoryType.PROCEDURAL]
        elif isinstance(type_filter, str):
            type_filter = [MemoryType(type_filter)]
        
        for item in self._cache.values():
            if item.meta.archived:
                continue
            
            if item.type not in type_filter:
                continue
            
            if item.type in [MemoryType.SEMANTIC, MemoryType.PROCEDURAL]:
                if item.meta.invalid_at and item.meta.invalid_at < datetime.now():
                    continue
            
            score = 0.0
            
            if item.embedding:
                sim_score = self._embedding_gen.cosine_similarity(query_embedding, item.embedding)
                score += sim_score * 0.4
            
            keyword_score = self._keyword_match(query, item.content_raw)
            score += keyword_score * 0.3
            
            if context.get("session_id") and item.session_id == context["session_id"]:
                score += 0.2
            
            time_filter = context.get("time_filter")
            if time_filter:
                cutoff = datetime.now() - timedelta(days=time_filter)
                if item.created_at >= cutoff:
                    score += 0.1
            
            if item.entities:
                query_entities = self._extract_query_entities(query)
                entity_match = len(set(item.entities) & set(query_entities))
                score += entity_match * 0.1
            
            if score > 0.1:
                candidates.append((score, item))
        
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        return [item for _, item in candidates[:limit]]
    
    async def _stage2_expand(
        self,
        candidates: list[MemoryItem],
        context: dict,
        max_hops: int = 2,
        max_nodes_per_hop: int = 5,
    ) -> list[MemoryItem]:
        """阶段2: 局部关联扩展"""
        expanded = {item.id: item for item in candidates}
        
        queue = list(candidates)
        visited = set(item.id for item in candidates)
        
        for hop in range(max_hops):
            if not queue:
                break
            
            next_queue = []
            
            for item in queue[:max_nodes_per_hop]:
                related_ids = self._relation_graph.get(item.id, [])
                
                for relation in related_ids[:max_nodes_per_hop]:
                    related_id = relation.get("target_id")
                    if related_id and related_id not in visited:
                        if related_id in self._cache:
                            related_item = self._cache[related_id]
                            if not related_item.meta.archived:
                                expanded[related_id] = related_item
                                visited.add(related_id)
                                next_queue.append(related_item)
            
            queue = next_queue
        
        return list(expanded.values())
    
    async def _stage3_rerank(
        self,
        candidates: list[MemoryItem],
        query: str,
        context: dict,
    ) -> list[RetrievalResult]:
        """阶段3: 重排"""
        results = []
        
        now = datetime.now()
        
        for item in candidates:
            relevance = self._calculate_relevance(item, query)
            
            age = (now - item.created_at).total_seconds()
            recency = 1.0 / (1.0 + age / 86400)
            
            confidence = item.meta.confidence
            
            verification_bonus = min(item.meta.success_reuse_count * 0.05, 0.3)
            
            task_significance = self._calculate_task_significance(item, context)
            
            path_quality = self._calculate_path_quality(item)
            
            type_match_bonus = 0.0
            preferred_types = context.get("preferred_types", [])
            if preferred_types and item.type in preferred_types:
                type_match_bonus = 0.15
            
            score = (
                relevance * 0.3 +
                recency * 0.2 +
                confidence * 0.2 +
                verification_bonus * 0.1 +
                task_significance * 0.15 +
                path_quality * 0.05 +
                type_match_bonus * 0.1
            )
            
            ambiguities = self._identify_ambiguities(item)
            evidence = self._extract_evidence(item, query)
            alternatives = self._find_alternatives(item, candidates)
            
            result = RetrievalResult(
                memory=item,
                score=score,
                relevance=relevance,
                recency=recency,
                confidence=confidence,
                path_quality=path_quality,
                evidence=evidence,
                ambiguities=ambiguities,
                alternatives=alternatives,
            )
            results.append(result)
        
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results
    
    def _keyword_match(self, query: str, content: str) -> float:
        """关键词匹配"""
        query_tokens = set(self._embedding_gen._TOKEN_RE.findall(query.lower()))
        content_tokens = set(self._embedding_gen._TOKEN_RE.findall(content.lower()))
        
        if not query_tokens or not content_tokens:
            return 0.0
        
        intersection = query_tokens & content_tokens
        return len(intersection) / len(query_tokens)
    
    def _extract_query_entities(self, query: str) -> list[str]:
        """提取查询中的实体"""
        entities = []
        mention_patterns = [r"@(\w+)", r"<@(\w+)>"]
        for pattern in mention_patterns:
            entities.extend(re.findall(pattern, query))
        return entities
    
    def _calculate_relevance(self, item: MemoryItem, query: str) -> float:
        """计算相关性"""
        query_lower = query.lower()
        content_lower = item.content_raw.lower()
        
        if query_lower in content_lower:
            return 1.0
        
        query_tokens = set(self._embedding_gen._TOKEN_RE.findall(query_lower))
        content_tokens = set(self._embedding_gen._TOKEN_RE.findall(content_lower))
        
        if not query_tokens:
            return 0.0
        
        overlap = len(query_tokens & content_tokens)
        return overlap / len(query_tokens)
    
    def _calculate_task_significance(self, item: MemoryItem, context: dict) -> float:
        """计算任务显著性"""
        significance = item.meta.salience
        
        task_type = context.get("task_type")
        if task_type and item.type == MemoryType.PROCEDURAL:
            if item.procedural and task_type.lower() in str(item.procedural.preconditions).lower():
                significance += 0.3
        
        return min(significance, 1.0)
    
    def _calculate_path_quality(self, item: MemoryItem) -> float:
        """计算路径质量"""
        relations = self._relation_graph.get(item.id, [])
        
        if not relations:
            return 0.0
        
        edge_types = [r.get("type") for r in relations]
        
        quality_indicators = ["temporal", "causal", "semantic"]
        quality_count = sum(1 for t in edge_types if t in quality_indicators)
        
        return min(quality_count / 3.0, 1.0)
    
    def _identify_ambiguities(self, item: MemoryItem) -> list[str]:
        """识别歧义"""
        ambiguities = []
        
        if item.meta.confidence < 0.6:
            ambiguities.append("low_confidence")
        
        if item.meta.clarity < 0.7:
            ambiguities.append("unclear_content")
        
        if item.meta.conflict_ids:
            ambiguities.append(f"conflicts_with_{len(item.meta.conflict_ids)}_memories")
        
        if item.type == MemoryType.SPECULATION:
            ambiguities.append("speculative_content")
        
        return ambiguities
    
    def _extract_evidence(self, item: MemoryItem, query: str) -> list[str]:
        """提取证据"""
        evidence = []
        
        if item.meta.access_count > 0:
            evidence.append(f"accessed_{item.meta.access_count}_times")
        
        if item.meta.success_reuse_count > 0:
            evidence.append(f"successfully_reused_{item.meta.success_reuse_count}_times")
        
        if item.last_verified_at:
            days_since_verify = (datetime.now() - item.last_verified_at).days
            evidence.append(f"verified_{days_since_verify}_days_ago")
        
        return evidence
    
    def _find_alternatives(self, item: MemoryItem, candidates: list[MemoryItem]) -> list[str]:
        """查找替代记忆"""
        alternatives = []
        
        for other in candidates:
            if other.id == item.id:
                continue
            
            if other.type == item.type:
                if other.embedding and item.embedding:
                    sim = self._embedding_gen.cosine_similarity(other.embedding, item.embedding)
                    if 0.5 < sim < 0.9:
                        alternatives.append(other.id)
        
        return alternatives[:3]
    
    async def add_memory(self, memory: MemoryItem) -> None:
        """添加记忆到索引"""
        if memory.embedding is None:
            memory.embedding = self._embedding_gen.generate(memory.content_raw)
        
        self._cache[memory.id] = memory
        
        self._save_to_disk(memory)
        
        logger.debug(f"Added memory {memory.id} to retrieval index")
    
    async def update_memory(self, memory: MemoryItem) -> None:
        """更新记忆"""
        if memory.id in self._cache:
            self._cache[memory.id] = memory
            await self._rebuild_file()
    
    async def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        if memory_id in self._cache:
            del self._cache[memory_id]
            
            if memory_id in self._relation_graph:
                del self._relation_graph[memory_id]
            
            await self._rebuild_file()
            return True
        return False
    
    async def add_relation(self, source_id: str, target_id: str, relation_type: str) -> None:
        """添加关联关系"""
        if source_id not in self._relation_graph:
            self._relation_graph[source_id] = []
        
        relation = {
            "target_id": target_id,
            "type": relation_type,
            "created_at": datetime.now().isoformat(),
        }
        
        existing = [r for r in self._relation_graph[source_id] if r.get("target_id") != target_id]
        existing.append(relation)
        self._relation_graph[source_id] = existing
    
    def get_all(self) -> list[MemoryItem]:
        """获取所有记忆"""
        return list(self._cache.values())
    
    def _load_from_disk(self) -> None:
        """从磁盘加载"""
        memory_file = self.storage_dir / "memories.jsonl"
        
        if not memory_file.exists():
            return
        
        with open(memory_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        data = eval(line)
                        memory = MemoryItem.from_dict(data)
                        self._cache[memory.id] = memory
                    except Exception as e:
                        logger.warning(f"Failed to load memory: {e}")
        
        relations_file = self.storage_dir / "relations.json"
        if relations_file.exists():
            import json
            with open(relations_file, "r", encoding="utf-8") as f:
                self._relation_graph = json.load(f)
    
    def _save_to_disk(self, memory: MemoryItem) -> None:
        """保存单条记忆到磁盘"""
        memory_file = self.storage_dir / "memories.jsonl"
        
        with open(memory_file, "a", encoding="utf-8") as f:
            f.write(repr(memory.to_dict()) + "\n")
    
    async def _rebuild_file(self) -> None:
        """重建索引文件"""
        memory_file = self.storage_dir / "memories.jsonl"
        
        with open(memory_file, "w", encoding="utf-8") as f:
            for memory in self._cache.values():
                f.write(repr(memory.to_dict()) + "\n")
        
        relations_file = self.storage_dir / "relations.json"
        import json
        with open(relations_file, "w", encoding="utf-8") as f:
            json.dump(self._relation_graph, f)
        
        logger.debug("Rebuilt memory index files")
