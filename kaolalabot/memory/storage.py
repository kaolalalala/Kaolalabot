"""Memory storage implementations for different memory levels."""

import json
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import xxhash
import numpy as np

from loguru import logger

from kaolalabot.memory.models import (
    Memory, WorkingMemory, EpisodicMemory, SemanticMemory,
    MemoryLevel, MemoryPriority
)


class MemoryStorage(ABC):
    """Abstract base class for memory storage."""
    
    @abstractmethod
    async def save(self, memory: Memory) -> None:
        pass
    
    @abstractmethod
    async def get(self, memory_id: str) -> Optional[Memory]:
        pass
    
    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        pass
    
    @abstractmethod
    async def search(self, query: str, limit: int = 10, **filters) -> list[Memory]:
        pass


class WorkingMemoryStorage(MemoryStorage):
    """Working memory storage - in-memory with FIFO eviction."""
    
    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        self._memories: list[WorkingMemory] = []
        self._index: dict[str, int] = {}
    
    async def save(self, memory: WorkingMemory) -> None:
        memory.updated_at = datetime.now()
        self._memories.append(memory)
        self._index[memory.id] = len(self._memories) - 1
        
        if len(self._memories) > self.max_size:
            removed = self._memories.pop(0)
            del self._index[removed.id]
            self._rebuild_index()
    
    async def get(self, memory_id: str) -> Optional[WorkingMemory]:
        idx = self._index.get(memory_id)
        if idx is not None and idx < len(self._memories):
            memory = self._memories[idx]
            memory.accessed_at = datetime.now()
            memory.access_count += 1
            return memory
        return None
    
    async def delete(self, memory_id: str) -> bool:
        if memory_id in self._index:
            idx = self._index[memory_id]
            del self._memories[idx]
            self._rebuild_index()
            return True
        return False
    
    async def search(self, query: str, limit: int = 10, **filters) -> list[WorkingMemory]:
        results = []
        query_lower = query.lower()
        for memory in self._memories:
            if query_lower in memory.content.lower():
                results.append(memory)
            if len(results) >= limit:
                break
        return results
    
    async def get_all(self) -> list[WorkingMemory]:
        return self._memories.copy()
    
    async def clear(self) -> None:
        self._memories.clear()
        self._index.clear()
    
    def _rebuild_index(self) -> None:
        self._index = {m.id: i for i, m in enumerate(self._memories)}


class EpisodicMemoryStorage(MemoryStorage):
    """Episodic memory storage - JSONL file based."""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = storage_dir / "episodic.jsonl"
        self._cache: dict[str, EpisodicMemory] = {}
        self._load_to_cache()
    
    async def save(self, memory: EpisodicMemory) -> None:
        memory_json = {
            "id": memory.id,
            "content": memory.content,
            "memory_level": memory.memory_level.value,
            "priority": memory.priority.value,
            "created_at": memory.created_at.isoformat(),
            "updated_at": memory.updated_at.isoformat(),
            "accessed_at": memory.accessed_at.isoformat(),
            "access_count": memory.access_count,
            "tags": memory.tags,
            "source_session": memory.source_session,
            "source_type": memory.source_type,
            "session_id": memory.session_id,
            "turn_index": memory.turn_index,
            "expires_at": memory.expires_at.isoformat() if memory.expires_at else None,
        }
        
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(memory_json, ensure_ascii=False) + "\n")
        
        self._cache[memory.id] = memory
    
    async def get(self, memory_id: str) -> Optional[EpisodicMemory]:
        return self._cache.get(memory_id)
    
    async def delete(self, memory_id: str) -> bool:
        if memory_id in self._cache:
            self._cache[memory_id].is_deleted = True
            await self._rebuild_file()
            return True
        return False
    
    async def search(self, query: str, limit: int = 10, session_id: Optional[str] = None, 
                     since: Optional[datetime] = None, **filters) -> list[EpisodicMemory]:
        results = []
        query_lower = query.lower()
        
        for memory in self._cache.values():
            if hasattr(memory, 'is_deleted') and memory.is_deleted:
                continue
            if session_id and memory.session_id != session_id:
                continue
            if since and memory.created_at < since:
                continue
            if query_lower in memory.content.lower():
                results.append(memory)
            if len(results) >= limit:
                break
        
        return results
    
    async def get_recent(self, days: int = 7, limit: int = 100) -> list[EpisodicMemory]:
        cutoff = datetime.now() - timedelta(days=days)
        return await self.search("", limit=limit, since=cutoff)
    
    async def clear(self) -> None:
        self._cache.clear()
        if self.file_path.exists():
            self.file_path.unlink()
    
    def _load_to_cache(self) -> None:
        if not self.file_path.exists():
            return
        
        with open(self.file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        data["memory_level"] = MemoryLevel(data.get("memory_level", "episodic"))
                        data["priority"] = MemoryPriority(data.get("priority", 2))
                        data["created_at"] = datetime.fromisoformat(data["created_at"])
                        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
                        data["accessed_at"] = datetime.fromisoformat(data["accessed_at"])
                        if data.get("expires_at"):
                            data["expires_at"] = datetime.fromisoformat(data["expires_at"])
                        memory = EpisodicMemory(**data)
                        self._cache[memory.id] = memory
                    except Exception as e:
                        logger.warning(f"Failed to load memory: {e}")
    
    async def _rebuild_file(self) -> None:
        with open(self.file_path, "w", encoding="utf-8") as f:
            for memory in self._cache.values():
                if hasattr(memory, 'is_deleted') and memory.is_deleted:
                    continue
                memory_json = {
                    "id": memory.id,
                    "content": memory.content,
                    "memory_level": memory.memory_level.value,
                    "priority": memory.priority.value,
                    "created_at": memory.created_at.isoformat(),
                    "updated_at": memory.updated_at.isoformat(),
                    "accessed_at": memory.accessed_at.isoformat(),
                    "access_count": memory.access_count,
                    "tags": memory.tags,
                    "source_session": memory.source_session,
                    "source_type": memory.source_type,
                    "session_id": memory.session_id,
                    "turn_index": memory.turn_index,
                    "expires_at": memory.expires_at.isoformat() if memory.expires_at else None,
                }
                f.write(json.dumps(memory_json, ensure_ascii=False) + "\n")


class SemanticMemoryStorage(MemoryStorage):
    """Semantic memory storage - Vector-based with simple hash embeddings."""
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.file_path = self.persist_directory / "semantic.jsonl"
        self._cache: dict[str, SemanticMemory] = {}
        self._load_to_cache()
    
    async def save(self, memory: SemanticMemory) -> None:
        if memory.embedding is None:
            memory.embedding = self._generate_embedding(memory.content)
        
        memory_json = {
            "id": memory.id,
            "content": memory.content,
            "memory_level": memory.memory_level.value,
            "priority": memory.priority.value,
            "created_at": memory.created_at.isoformat(),
            "updated_at": memory.updated_at.isoformat(),
            "accessed_at": memory.accessed_at.isoformat(),
            "access_count": memory.access_count,
            "tags": memory.tags,
            "embedding": memory.embedding,
            "source_session": memory.source_session,
            "source_type": memory.source_type,
            "title": memory.title,
            "summary": memory.summary,
            "is_fact": memory.is_fact,
            "confidence": memory.confidence,
        }
        
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(memory_json, ensure_ascii=False) + "\n")
        
        self._cache[memory.id] = memory
    
    async def get(self, memory_id: str) -> Optional[SemanticMemory]:
        return self._cache.get(memory_id)
    
    async def delete(self, memory_id: str) -> bool:
        if memory_id in self._cache:
            del self._cache[memory_id]
            await self._rebuild_file()
            return True
        return False
    
    async def search(self, query: str, limit: int = 10, **filters) -> list[SemanticMemory]:
        if not query:
            return list(self._cache.values())[:limit]
        
        query_embedding = self._generate_embedding(query)
        
        results = []
        for memory in self._cache.values():
            if memory.embedding:
                similarity = self._cosine_similarity(query_embedding, memory.embedding)
                results.append((similarity, memory))
        
        results.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in results[:limit]]
    
    def _generate_embedding(self, text: str) -> list[float]:
        # Lightweight lexical hashing embedding:
        # - supports both Latin words and single CJK characters
        # - stable and dependency-free
        # - much better recall than fixed 8-byte text hash
        vec = np.zeros(self._EMBED_DIM, dtype=np.float32)
        tokens = self._TOKEN_RE.findall(text.lower())
        if not tokens:
            return vec.tolist()

        for token in tokens:
            idx = xxhash.xxh32(token.encode("utf-8")).intdigest() % self._EMBED_DIM
            vec[idx] += 1.0

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()
    
    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        a = np.array(a)
        b = np.array(b)
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot_product / (norm_a * norm_b))
    
    async def clear(self) -> None:
        self._cache.clear()
        if self.file_path.exists():
            self.file_path.unlink()
    
    def _load_to_cache(self) -> None:
        if not self.file_path.exists():
            return
        
        with open(self.file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        data["memory_level"] = MemoryLevel(data.get("memory_level", "semantic"))
                        data["priority"] = MemoryPriority(data.get("priority", 2))
                        data["created_at"] = datetime.fromisoformat(data["created_at"])
                        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
                        data["accessed_at"] = datetime.fromisoformat(data["accessed_at"])
                        memory = SemanticMemory(**data)
                        self._cache[memory.id] = memory
                    except Exception as e:
                        logger.warning(f"Failed to load semantic memory: {e}")
    
    async def _rebuild_file(self) -> None:
        with open(self.file_path, "w", encoding="utf-8") as f:
            for memory in self._cache.values():
                memory_json = {
                    "id": memory.id,
                    "content": memory.content,
                    "memory_level": memory.memory_level.value,
                    "priority": memory.priority.value,
                    "created_at": memory.created_at.isoformat(),
                    "updated_at": memory.updated_at.isoformat(),
                    "accessed_at": memory.accessed_at.isoformat(),
                    "access_count": memory.access_count,
                    "tags": memory.tags,
                    "embedding": memory.embedding,
                    "source_session": memory.source_session,
                    "source_type": memory.source_type,
                    "title": memory.title,
                    "summary": memory.summary,
                    "is_fact": memory.is_fact,
                    "confidence": memory.confidence,
                }
                f.write(json.dumps(memory_json, ensure_ascii=False) + "\n")
    _EMBED_DIM = 128
    _TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
