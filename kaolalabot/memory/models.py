"""Memory models for layered memory system V2."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class MemoryType(Enum):
    """记忆类型"""
    SENSORY = "sensory"       # 感官缓冲
    WORKING = "working"       # 工作记忆
    EPISODIC = "episodic"     # 情景记忆
    SEMANTIC = "semantic"     # 语义记忆
    PROCEDURAL = "procedural" # 程序记忆
    SPECULATION = "speculation" # 推测


class InputCategory(Enum):
    """输入分类"""
    FACT = "fact"                     # 事实
    EVENT = "event"                   # 事件
    SKILL_EXPERIENCE = "skill_exp"    # 技能经验
    TEMP_STATE = "temp_state"         # 临时状态
    SPECULATION = "speculation"      # 推测
    NOISE = "noise"                   # 噪声


class ContentSource(Enum):
    """记忆来源"""
    USER_INPUT = "user_input"
    TOOL_RETURN = "tool_return"
    ENVIRONMENT = "environment"
    LOG = "log"
    EXTRACTION = "extraction"


class PrivacyLevel(Enum):
    """隐私级别"""
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    PRIVATE = 3


# 向后兼容
class MemoryLevel(Enum):
    """记忆级别 (向后兼容)"""
    WORKING = "working"      # 工作记忆
    EPISODIC = "episodic"    # 情景记忆
    SEMANTIC = "semantic"    # 语义记忆


class MemoryPriority(Enum):
    """记忆优先级 (向后兼容)"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Memory:
    """Backward-compatible memory base model."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    memory_level: MemoryLevel = MemoryLevel.WORKING
    priority: MemoryPriority = MemoryPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    tags: list[str] = field(default_factory=list)
    source_session: str | None = None
    source_type: str = "user_input"
    is_deleted: bool = False


@dataclass
class WorkingMemory(Memory):
    """Backward-compatible working memory model."""

    memory_level: MemoryLevel = MemoryLevel.WORKING
    role: str = "user"


@dataclass
class EpisodicMemory(Memory):
    """Backward-compatible episodic memory model."""

    memory_level: MemoryLevel = MemoryLevel.EPISODIC
    session_id: str = "default"
    turn_index: int = 0
    expires_at: Optional[datetime] = None


@dataclass
class SemanticMemory(Memory):
    """Backward-compatible semantic memory model."""

    memory_level: MemoryLevel = MemoryLevel.SEMANTIC
    embedding: Optional[list[float]] = None
    title: str = ""
    summary: str = ""
    is_fact: bool = False
    confidence: float = 1.0


@dataclass
class MetaInfo:
    """元信息 - 记忆治理信息"""
    source: ContentSource = ContentSource.USER_INPUT
    confidence: float = 1.0
    salience: float = 0.5
    clarity: float = 1.0
    valid_at: Optional[datetime] = field(default_factory=datetime.now)
    invalid_at: Optional[datetime] = None
    last_verified_at: Optional[datetime] = None
    access_count: int = 0
    success_reuse_count: int = 0
    failure_reuse_count: int = 0
    conflict_ids: list[str] = field(default_factory=list)
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL
    archived: bool = False

    def to_dict(self) -> dict:
        return {
            "source": self.source.value,
            "confidence": self.confidence,
            "salience": self.salience,
            "clarity": self.clarity,
            "valid_at": self.valid_at.isoformat() if self.valid_at else None,
            "invalid_at": self.invalid_at.isoformat() if self.invalid_at else None,
            "last_verified_at": self.last_verified_at.isoformat() if self.last_verified_at else None,
            "access_count": self.access_count,
            "success_reuse_count": self.success_reuse_count,
            "failure_reuse_count": self.failure_reuse_count,
            "conflict_ids": self.conflict_ids,
            "privacy_level": self.privacy_level.value,
            "archived": self.archived,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MetaInfo":
        if data.get("valid_at"):
            data["valid_at"] = datetime.fromisoformat(data["valid_at"])
        if data.get("invalid_at"):
            data["invalid_at"] = datetime.fromisoformat(data["invalid_at"])
        if data.get("last_verified_at"):
            data["last_verified_at"] = datetime.fromisoformat(data["last_verified_at"])
        if data.get("source"):
            data["source"] = ContentSource(data["source"])
        if data.get("privacy_level"):
            data["privacy_level"] = PrivacyLevel(data["privacy_level"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ProceduralInfo:
    """程序记忆额外信息"""
    preconditions: list[str] = field(default_factory=list)
    action_steps: list[str] = field(default_factory=list)
    observables: list[str] = field(default_factory=list)
    failure_modes: list[str] = field(default_factory=list)
    recovery_plan: list[str] = field(default_factory=list)
    tool_dependencies: list[str] = field(default_factory=list)
    success_rate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "preconditions": self.preconditions,
            "action_steps": self.action_steps,
            "observables": self.observables,
            "failure_modes": self.failure_modes,
            "recovery_plan": self.recovery_plan,
            "tool_dependencies": self.tool_dependencies,
            "success_rate": self.success_rate,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProceduralInfo":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class MemoryItem:
    """统一记忆项"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: MemoryType = MemoryType.WORKING

    content_raw: str = ""
    content_structured: Optional[dict] = None
    summary: str = ""

    embedding: Optional[list[float]] = None

    entities: list[str] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)

    created_at: datetime = field(default_factory=datetime.now)
    last_accessed_at: datetime = field(default_factory=datetime.now)
    last_verified_at: Optional[datetime] = None

    meta: MetaInfo = field(default_factory=MetaInfo)

    procedural: Optional[ProceduralInfo] = None

    task_id: Optional[str] = None
    session_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "content_raw": self.content_raw,
            "content_structured": self.content_structured,
            "summary": self.summary,
            "embedding": self.embedding,
            "entities": self.entities,
            "relations": self.relations,
            "created_at": self.created_at.isoformat(),
            "last_accessed_at": self.last_accessed_at.isoformat(),
            "last_verified_at": self.last_verified_at.isoformat() if self.last_verified_at else None,
            "meta": self.meta.to_dict(),
            "procedural": self.procedural.to_dict() if self.procedural else None,
            "task_id": self.task_id,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryItem":
        if data.get("type"):
            data["type"] = MemoryType(data["type"])
        if data.get("created_at"):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("last_accessed_at"):
            data["last_accessed_at"] = datetime.fromisoformat(data["last_accessed_at"])
        if data.get("last_verified_at") and data["last_verified_at"]:
            data["last_verified_at"] = datetime.fromisoformat(data["last_verified_at"])
        if data.get("meta"):
            data["meta"] = MetaInfo.from_dict(data["meta"])
        if data.get("procedural"):
            data["procedural"] = ProceduralInfo.from_dict(data["procedural"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SensoryBuffer:
    """感官缓冲 - 短暂保存原始输入"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    source: ContentSource = ContentSource.USER_INPUT
    created_at: datetime = field(default_factory=datetime.now)
    processed: bool = False


@dataclass
class RetrievalResult:
    """检索结果"""
    memory: MemoryItem
    score: float = 0.0
    relevance: float = 0.0
    recency: float = 0.0
    confidence: float = 0.0
    path_quality: float = 0.0

    evidence: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "memory": self.memory.to_dict(),
            "score": self.score,
            "relevance": self.relevance,
            "recency": self.recency,
            "confidence": self.confidence,
            "path_quality": self.path_quality,
            "evidence": self.evidence,
            "ambiguities": self.ambiguities,
            "alternatives": self.alternatives,
        }


@dataclass
class IngestionCandidate:
    """待摄入的记忆候选"""
    content: str
    category: InputCategory
    source: ContentSource
    raw_score: float = 0.5

    metadata: dict = field(default_factory=dict)

    entities: list[str] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)

    suggested_type: Optional[MemoryType] = None


@dataclass
class TaskLog:
    """任务日志 - 用于程序记忆提炼"""
    task_id: str
    task_type: str
    start_time: datetime
    end_time: Optional[datetime] = None

    steps: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)

    success: bool = False
    error: Optional[str] = None
    recovery_actions: list[str] = field(default_factory=list)

    observations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "steps": self.steps,
            "tool_calls": self.tool_calls,
            "success": self.success,
            "error": self.error,
            "recovery_actions": self.recovery_actions,
            "observations": self.observations,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskLog":
        if data.get("start_time"):
            data["start_time"] = datetime.fromisoformat(data["start_time"])
        if data.get("end_time") and data["end_time"]:
            data["end_time"] = datetime.fromisoformat(data["end_time"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
