"""RAG (Retrieval Augmented Generation) knowledge enhancement system."""

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class KnowledgeChunk:
    """A chunk of knowledge document."""
    id: str
    content: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None
    created_at: datetime = field(default_factory=datetime.now)


class SimpleVectorStore:
    """
    Simple in-memory vector store for knowledge retrieval.
    
    Uses TF-IDF style similarity for demonstration.
    In production, replace with proper vector database like ChromaDB.
    """

    def __init__(self):
        self._chunks: list[KnowledgeChunk] = []
        self._index: dict[str, set[str]] = {}

    def add_chunk(self, chunk: KnowledgeChunk) -> None:
        """Add a chunk to the store."""
        self._chunks.append(chunk)
        
        words = self._tokenize(chunk.content)
        for word in words:
            if word not in self._index:
                self._index[word] = set()
            self._index[word].add(chunk.id)

    def search(self, query: str, top_k: int = 5) -> list[KnowledgeChunk]:
        """Search for relevant chunks."""
        query_words = self._tokenize(query)
        
        if not query_words:
            return []
        
        scores: dict[str, float] = {}
        for word in query_words:
            if word in self._index:
                for chunk_id in self._index[word]:
                    scores[chunk_id] = scores.get(chunk_id, 0) + 1
        
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for chunk_id, score in sorted_ids[:top_k]:
            for chunk in self._chunks:
                if chunk.id == chunk_id:
                    results.append(chunk)
                    break
        
        return results

    def _tokenize(self, text: str) -> set[str]:
        """Simple tokenization."""
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        tokens = text.split()
        return {t for t in tokens if len(t) > 1}

    def get_chunk_count(self) -> int:
        """Get total chunk count."""
        return len(self._chunks)


class KnowledgeIngestor:
    """
    Knowledge document ingestor.
    
    Parses and chunks documents for RAG.
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def ingest_text(
        self,
        text: str,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[KnowledgeChunk]:
        """Ingest plain text."""
        chunks = []
        
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunk_text = text[i:i + self.chunk_size]
            
            chunk_id = hashlib.md5(
                f"{source}:{i}:{chunk_text[:50]}".encode()
            ).hexdigest()
            
            chunk = KnowledgeChunk(
                id=chunk_id,
                content=chunk_text.strip(),
                source=source,
                metadata=metadata or {},
            )
            chunks.append(chunk)
        
        return chunks

    def ingest_file(
        self,
        file_path: Path,
        metadata: dict[str, Any] | None = None,
    ) -> list[KnowledgeChunk]:
        """Ingest a file."""
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return []
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            
            return self.ingest_text(
                text,
                source=str(file_path),
                metadata=metadata or {"type": file_path.suffix},
            )
        except Exception as e:
            logger.error(f"Failed to ingest file {file_path}: {e}")
            return []


class RAGEngine:
    """
    Retrieval Augmented Generation Engine.
    
    Provides knowledge retrieval and context enhancement.
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.vector_store = SimpleVectorStore()
        self.ingestor = KnowledgeIngestor(chunk_size, chunk_overlap)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the RAG engine and load knowledge base."""
        if self._initialized:
            return
        
        await self._load_knowledge_base()
        self._initialized = True
        logger.info(f"RAG engine initialized with {self.vector_store.get_chunk_count()} chunks")

    async def _load_knowledge_base(self) -> None:
        """Load knowledge base from workspace."""
        workspace = Path("D:/ai/kaolalabot/workspace")
        knowledge_dir = workspace / "knowledge"
        
        if not knowledge_dir.exists():
            knowledge_dir.mkdir(parents=True, exist_ok=True)
            
            sample_knowledge = {
                "about_kaolalabot.md": """# Kaolalabot

Kaolalabot 是一个基于 AI 的多功能 Agent 框架。

## 主要功能
- 消息总线架构
- 记忆系统
- 多提供商支持
- 深度思考模式
- 工具执行

## 使用方法
请直接与机器人对话，它会理解您的意图并提供帮助。
"""
            }
            
            for filename, content in sample_knowledge.items():
                file_path = knowledge_dir / filename
                file_path.write_text(content, encoding="utf-8")
        
        for file_path in knowledge_dir.glob("*.md"):
            chunks = self.ingestor.ingest_file(file_path)
            for chunk in chunks:
                self.vector_store.add_chunk(chunk)

    async def retrieve(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[str]:
        """Retrieve relevant knowledge for a query."""
        if not self._initialized:
            await self.initialize()
        
        chunks = self.vector_store.search(query, top_k=top_k)
        return [chunk.content for chunk in chunks]

    async def augment_prompt(
        self,
        user_query: str,
        max_context_length: int = 1000,
    ) -> str:
        """Augment user prompt with relevant knowledge."""
        relevant_chunks = await self.retrieve(user_query, top_k=3)
        
        if not relevant_chunks:
            return ""
        
        context = "\n\n".join(relevant_chunks)
        
        if len(context) > max_context_length:
            context = context[:max_context_length] + "..."
        
        return f"\n\n参考知识:\n{context}\n"

    def add_knowledge(
        self,
        content: str,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add new knowledge to the store."""
        chunks = self.ingestor.ingest_text(content, source, metadata)
        for chunk in chunks:
            self.vector_store.add_chunk(chunk)
        logger.info(f"Added {len(chunks)} chunks from {source}")


class RAGMiddleware:
    """
    RAG middleware for integrating knowledge retrieval.
    
    Can be integrated into the agent loop.
    """

    def __init__(self, rag_engine: RAGEngine | None = None):
        self.rag_engine = rag_engine or RAGEngine()

    async def initialize(self) -> None:
        """Initialize the RAG middleware."""
        await self.rag_engine.initialize()

    async def process_query(
        self,
        user_query: str,
    ) -> tuple[str, list[str]]:
        """
        Process query and return augmented query with sources.
        
        Returns (augmented_query, sources)
        """
        relevant_knowledge = await self.rag_engine.retrieve(user_query)
        
        if not relevant_knowledge:
            return user_query, []
        
        augmented = user_query
        if relevant_knowledge:
            context = "\n\n".join(relevant_knowledge[:2])
            augmented = f"{user_query}\n\n请参考以下知识:\n{context}"
        
        sources = list(set(c.source for c in self.rag_engine.vector_store._chunks 
                         if any(c.id == chunk.id for chunk in self.rag_engine.vector_store.search(user_query))))
        
        return augmented, sources
