# Memory 模块 - 记忆系统

> 记忆是智能的基础。kaolalabot 的记忆系统模拟人类记忆的三层结构，实现持久化、可检索的对话历史管理。

## 📖 目录

- [功能说明](#功能说明)
- [记忆模型](#记忆模型)
- [架构设计](#架构设计)
- [使用方法](#使用方法)
- [API 参考](#api-参考)
- [实现原理](#实现原理)
- [最佳实践](#最佳实践)

---

## 🎯 功能说明

### 核心职责

1. **持久化对话历史**：保存所有对话记录
2. **上下文检索**：快速查找相关记忆
3. **记忆分层管理**：工作记忆、情景记忆、语义记忆
4. **记忆整合与淘汰**：自动清理过期记忆

### 为什么需要记忆系统？

#### 没有记忆的问题

```python
# ❌ 无状态对话
class StatelessAgent:
    def chat(self, message):
        # 每次都从零开始
        response = llm.generate(message)
        return response

# 用户：我叫小明
# Agent: 你好！
# 用户：我刚才说了什么？
# Agent: 抱歉，我不记得了 😞
```

#### 有记忆的优势

```python
# ✅ 有状态对话
class StatefulAgent:
    def __init__(self, memory):
        self.memory = memory
    
    async def chat(self, message, session_id):
        # 检索相关记忆
        context = await self.memory.recall(message, session_id)
        
        # 构建带上下文的 prompt
        prompt = f"Context: {context}\nUser: {message}"
        response = await llm.generate(prompt)
        
        # 保存新记忆
        await self.memory.add(message, session_id, role="user")
        await self.memory.add(response, session_id, role="assistant")
        
        return response

# 用户：我叫小明
# Agent: 你好小明！
# 用户：我刚才说了什么？
# Agent: 你刚才说你叫小明呀 😊
```

---

## 🧠 记忆模型

### 三层记忆结构

受人类记忆启发，kaolalabot 采用三层记忆模型：

```
┌─────────────────────────────────────────┐
│     工作记忆 (Working Memory)           │
│  - 短期存储（最近 20 条消息）             │
│  - 快速访问                             │
│  - 会话结束后清除                       │
│  - 类似人类的"短期记忆"                 │
└─────────────────────────────────────────┘
                ↓ 固化
┌─────────────────────────────────────────┐
│     情景记忆 (Episodic Memory)          │
│  - 具体事件（对话历史）                  │
│  - 按会话组织                           │
│  - 保留 30 天（可配置）                   │
│  - 类似人类的"情景记忆"                 │
└─────────────────────────────────────────┘
                ↓ 抽象
┌─────────────────────────────────────────┐
│     语义记忆 (Semantic Memory)          │
│  - 抽象知识（事实、概念）                │
│  - 向量检索                             │
│  - 长期保留                             │
│  - 类似人类的"语义记忆"                 │
└─────────────────────────────────────────┘
```

### 记忆类型详解

#### 1. 工作记忆 (Working Memory)

**特点**：
- 🚀 **速度快**：内存存储，微秒级访问
- ⏱️ **容量有限**：默认 20 条消息
- 🔄 **临时性**：会话结束即清除
- 📍 **上下文相关**：当前对话的直接上下文

**使用场景**：
- 多轮对话的即时上下文
- 最近的用户输入和助手回复
- 临时变量和状态

**示例**：
```python
{
  "session_id": "session_123",
  "messages": [
    {"role": "user", "content": "帮我写个 Python 函数"},
    {"role": "assistant", "content": "好的，什么功能的函数？"},
    {"role": "user", "content": "计算斐波那契数列"},
  ]
}
```

#### 2. 情景记忆 (Episodic Memory)

**特点**：
- 📁 **按会话组织**：每个会话一个文件
- 📅 **时间衰减**：30 天后自动删除
- 🔍 **可检索**：支持时间范围和关键词搜索
- 💾 **持久化**：JSONL 文件格式

**使用场景**：
- 历史对话记录
- 用户偏好和行为模式
- 特定事件的详细信息

**示例**：
```jsonl
{"id": "mem_001", "session_id": "session_123", "content": "用户询问 Python 函数", "timestamp": "2026-03-04T10:00:00Z", "tags": ["coding", "python"]}
{"id": "mem_002", "session_id": "session_123", "content": "生成斐波那契函数", "timestamp": "2026-03-04T10:01:00Z", "tags": ["coding", "algorithm"]}
```

#### 3. 语义记忆 (Semantic Memory)

**特点**：
- 🧠 **抽象知识**：从具体事件中提取的一般知识
- 🔬 **向量表示**：使用嵌入模型编码
- 🔎 **语义检索**：基于相似度搜索
- ♾️ **长期保留**：除非手动删除

**使用场景**：
- 用户画像和偏好
- 领域知识和事实
- 从对话中学习到的模式

**示例**：
```python
{
  "id": "sem_001",
  "content": "用户小明喜欢 Python 编程",
  "embedding": [0.1, -0.2, 0.3, ...],  # 向量表示
  "tags": ["user_preference", "programming"],
  "confidence": 0.95
}
```

---

## 🏗️ 架构设计

### 组件图

```
┌─────────────────────────────────────────────────────┐
│                MemoryManager                        │
│  - 统一接口                                         │
│  - 协调三层记忆                                     │
│  - 记忆整合和淘汰                                   │
└────────────┬────────────────────────────────────────┘
             │
    ┌────────┼────────┐
    │        │        │
    ↓        ↓        ↓
┌────────┐ ┌────────┐ ┌────────────┐
│Working │ │Episodic│ │Semantic    │
│Storage │ │Storage │ │Storage     │
│        │ │        │ │            │
│内存缓存│ │JSONL   │ │Chroma DB   │
│        │ │文件    │ │向量数据库  │
└────────┘ └────────┘ └────────────┘
```

### 数据流

#### 添加记忆

```
用户消息
   ↓
MemoryManager.add()
   ↓
根据 memory_level 选择存储层
   ↓
┌─────────────┬─────────────┬──────────────┐
│WorkingMemory│EpisodicMem │SemanticMem   │
│  添加到列表  │ 写入 JSONL  │ 计算 embedding│
│             │            │ 存入 Chroma  │
└─────────────┴─────────────┴──────────────┘
```

#### 检索记忆

```
检索请求
   ↓
MemoryManager.recall(query)
   ↓
并行检索三层记忆
   ↓
┌─────────────┬─────────────┬──────────────┐
│Working:     │Episodic:   │Semantic:     │
│最近 N 条     │关键词匹配  │向量相似度    │
└─────────────┴─────────────┴──────────────┘
   ↓
合并结果并排序
   ↓
返回最相关的记忆
```

---

## 📖 使用方法

### 初始化

```python
from pathlib import Path
from kaolalabot.memory import MemoryManager

# 创建记忆管理器
memory = MemoryManager(
    workspace=Path("./workspace"),
    working_capacity=20,        # 工作记忆容量
    episodic_retention_days=30  # 情景记忆保留天数
)
```

### 添加记忆

```python
# 添加到工作记忆（默认）
await memory.add(
    content="用户想要学习 Python",
    memory_level="working",
    session_id="session_123"
)

# 添加到情景记忆
await memory.add(
    content="用户询问了斐波那契数列的实现",
    memory_level="episodic",
    session_id="session_123",
    tags=["coding", "python", "algorithm"]
)

# 添加到语义记忆
await memory.add(
    content="用户对编程感兴趣，正在学习 Python",
    memory_level="semantic",
    title="用户兴趣",
    summary="Python 初学者",
    tags=["user_profile", "interests"]
)
```

### 检索记忆

```python
# 检索相关记忆
memories = await memory.recall(
    query="Python 编程",
    session_id="session_123",
    limit=5  # 返回最多 5 条
)

for mem in memories:
    print(f"[{mem.level}] {mem.content}")
```

### 构建对话上下文

```python
async def build_context(session_id: str, query: str) -> str:
    """构建对话上下文"""
    
    # 检索相关记忆
    memories = await memory.recall(query, session_id)
    
    # 格式化为上下文
    context_parts = []
    for mem in memories:
        context_parts.append(f"- {mem.content}")
    
    context = "\n".join(context_parts)
    
    return f"Relevant context:\n{context}"
```

---

## 📚 API 参考

### MemoryManager

```python
class MemoryManager:
    async def add(
        self,
        content: str,
        memory_level: str = "working",
        priority: int = 2,
        **metadata
    ) -> Memory:
        """
        添加记忆
        
        Args:
            content: 记忆内容
            memory_level: 记忆层级 ("working", "episodic", "semantic")
            priority: 优先级 (1-5, 5 最高)
            **metadata: 额外元数据
        
        Returns:
            Memory 对象
        """
    
    async def recall(
        self,
        query: str,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> list[Memory]:
        """
        检索记忆
        
        Args:
            query: 查询文本
            session_id: 会话 ID（可选）
            limit: 返回数量限制
        
        Returns:
            记忆列表，按相关性排序
        """
    
    async def clear(
        self,
        memory_level: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> None:
        """
        清除记忆
        
        Args:
            memory_level: 指定层级（None 表示全部）
            session_id: 指定会话（None 表示全部）
        """
    
    async def cleanup(self) -> None:
        """
        清理过期记忆
        
        删除超过保留期的情景记忆
        """
```

### Memory 模型

```python
class Memory(BaseModel):
    id: str                    # 唯一标识
    content: str               # 记忆内容
    level: MemoryLevel         # 记忆层级
    priority: MemoryPriority   # 优先级
    created_at: datetime       # 创建时间
    metadata: dict             # 元数据

class WorkingMemory(Memory):
    role: str                  # "user" 或 "assistant"
    source_session: str        # 来源会话

class EpisodicMemory(Memory):
    session_id: str            # 会话 ID
    expires_at: datetime       # 过期时间
    tags: list[str]            # 标签

class SemanticMemory(Memory):
    title: str                 # 标题
    summary: str               # 摘要
    is_fact: bool              # 是否为事实
    confidence: float          # 置信度
    tags: list[str]            # 标签
    embedding: list[float]     # 向量表示
```

---

## 🔍 实现原理

### 1. 工作记忆 - 循环缓冲区

```python
class WorkingMemoryStorage:
    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        self.memories: deque[WorkingMemory] = deque(maxlen=max_size)
    
    async def save(self, memory: WorkingMemory):
        """添加到队列，超出容量时自动淘汰最旧的"""
        self.memories.append(memory)
    
    async def get_recent(self, limit: int = 10) -> list[WorkingMemory]:
        """获取最近的记忆"""
        return list(self.memories)[-limit:]
```

**设计要点**：
- 使用 `deque` 实现高效的 FIFO 队列
- `maxlen` 参数自动限制容量
- O(1) 时间复杂度的添加和删除

### 2. 情景记忆 - JSONL 存储

```python
class EpisodicMemoryStorage:
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_file(self, session_id: str) -> Path:
        """获取会话文件路径"""
        return self.storage_dir / f"{session_id}.jsonl"
    
    async def save(self, memory: EpisodicMemory):
        """追加到 JSONL 文件"""
        file_path = self._get_file(memory.session_id)
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(memory.model_dump_json() + '\n')
    
    async def search(
        self,
        session_id: str,
        keywords: list[str],
        time_range: tuple[datetime, datetime] = None
    ) -> list[EpisodicMemory]:
        """搜索情景记忆"""
        file_path = self._get_file(session_id)
        results = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                memory = EpisodicMemory.model_validate_json(line)
                
                # 关键词匹配
                if any(kw in memory.content for kw in keywords):
                    results.append(memory)
        
        return results
```

**设计要点**：
- JSONL 格式：每行一个 JSON 对象
- 按会话分文件：便于管理和清理
- 支持增量写入：无需加载整个文件

### 3. 语义记忆 - 向量检索

```python
class SemanticMemoryStorage:
    def __init__(self, chroma_path: str):
        import chromadb
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_or_create_collection(
            name="semantic_memories",
            metadata={"hnsw:space": "cosine"}  # 余弦相似度
        )
    
    async def save(self, memory: SemanticMemory):
        """计算 embedding 并存储"""
        # 使用嵌入模型
        embedding = await self._compute_embedding(memory.content)
        
        # 存入 ChromaDB
        self.collection.add(
            ids=[memory.id],
            documents=[memory.content],
            embeddings=[embedding],
            metadatas=[memory.model_dump()]
        )
    
    async def search(self, query: str, limit: int = 10) -> list[SemanticMemory]:
        """向量相似度搜索"""
        query_embedding = await self._compute_embedding(query)
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit
        )
        
        return [SemanticMemory(**meta) for meta in results['metadatas'][0]]
```

**设计要点**：
- ChromaDB：轻量级向量数据库
- 余弦相似度：衡量语义相关性
- 持久化存储：支持重启后恢复

---

## 💡 最佳实践

### 1. 合理选择记忆层级

```python
# ✅ 推荐：根据用途选择
# 临时上下文 → 工作记忆
await memory.add("用户刚说的话", level="working")

# 历史对话 → 情景记忆
await memory.add("昨天的对话内容", level="episodic")

# 学到的知识 → 语义记忆
await memory.add("用户喜欢 Python", level="semantic")

# ❌ 避免：全部存到同一层
await memory.add("所有内容", level="working")  # 会快速被淘汰
```

### 2. 使用标签增强检索

```python
# ✅ 推荐：添加描述性标签
await memory.add(
    content="用户询问斐波那契数列",
    level="episodic",
    tags=["coding", "python", "algorithm", "fibonacci"]
)

# ❌ 避免：不使用标签或使用模糊标签
await memory.add("内容", tags=["tag1", "tag2"])  # 无意义
```

### 3. 定期清理过期记忆

```python
# ✅ 推荐：定期清理
async def maintenance_task():
    while True:
        await memory.cleanup()  # 清理过期记忆
        await asyncio.sleep(3600)  # 每小时执行一次

# ❌ 避免：从不清理
# 导致磁盘空间浪费，检索变慢
```

### 4. 优化检索性能

```python
# ✅ 推荐：限制检索范围
memories = await memory.recall(
    query="Python",
    session_id="session_123",  # 限定会话
    limit=5  # 限制数量
)

# ❌ 避免：无限制检索
memories = await memory.recall("Python")  # 可能返回大量结果
```

### 5. 记忆整合策略

```python
# ✅ 推荐：定期整合工作记忆到情景记忆
async def consolidate_memories():
    # 从工作记忆中提取重要信息
    working_memories = await memory.working.get_recent(limit=20)
    
    # 使用 LLM 总结
    summary = await llm.summarize([m.content for m in working_memories])
    
    # 保存到情景记忆
    await memory.add(summary, level="episodic")
    
    # 清空工作记忆
    await memory.working.clear()
```

---

## 🐛 常见问题

### Q1: 记忆太多导致检索慢怎么办？

**A**: 分层检索 + 缓存热点

```python
class OptimizedMemoryManager(MemoryManager):
    def __init__(self):
        super().__init__()
        self.cache = {}  # 简单缓存
    
    async def recall(self, query: str, **kwargs):
        # 检查缓存
        cache_key = f"{query}:{kwargs.get('session_id')}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # 只检索工作记忆和最近的情景记忆
        results = await super().recall(query, **kwargs)
        
        # 缓存结果
        self.cache[cache_key] = results[:10]
        return self.cache[cache_key]
```

### Q2: 如何保护隐私数据？

**A**: 加密敏感记忆

```python
from cryptography.fernet import Fernet

class EncryptedMemoryStorage(EpisodicMemoryStorage):
    def __init__(self, *args, encryption_key: bytes):
        super().__init__(*args)
        self.cipher = Fernet(encryption_key)
    
    async def save(self, memory):
        # 检测敏感内容
        if self._is_sensitive(memory.content):
            # 加密
            memory.content = self.cipher.encrypt(
                memory.content.encode()
            ).decode()
            memory.metadata['encrypted'] = True
        
        await super().save(memory)
    
    def _is_sensitive(self, content: str) -> bool:
        # 简单检测：包含邮箱、电话等
        import re
        patterns = [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            r'\b\d{11}\b'  # 手机号
        ]
        return any(re.search(p, content) for p in patterns)
```

### Q3: 如何实现跨会话记忆共享？

**A**: 使用语义记忆

```python
# 会话 A 学到的知识
await memory.add(
    "用户小明喜欢 Python 胜过 Java",
    level="semantic",
    tags=["user_preference"],
    metadata={"user_id": "user_123"}
)

# 会话 B 检索
memories = await memory.recall(
    query="编程语言偏好",
    session_id="session_456"  # 不同会话
)
# 可以检索到语义记忆
```

---

## 📚 相关资源

- [人类记忆模型](https://en.wikipedia.org/wiki/Atkinson%E2%80%93Shiffrin_memory_model)
- [ChromaDB 文档](https://docs.trychroma.com/)
- [向量数据库对比](https://www.pinecone.io/learn/vector-database/)

---

**最后更新**: 2026-03-04

**维护者**: kaolalabot Team
