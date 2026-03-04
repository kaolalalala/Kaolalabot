"""Memory module - Layered memory system V2."""

from kaolalabot.memory.models import (
    Memory,
    WorkingMemory,
    EpisodicMemory,
    SemanticMemory,
    MemoryItem,
    MemoryType,
    InputCategory,
    ContentSource,
    PrivacyLevel,
    MetaInfo,
    ProceduralInfo,
    SensoryBuffer,
    RetrievalResult,
    IngestionCandidate,
    TaskLog,
    MemoryLevel,
    MemoryPriority,
)

from kaolalabot.memory.manager_v2 import MemoryManagerV2
from kaolalabot.memory.gate import IngestionGate, SensoryBufferManager
from kaolalabot.memory.retrieval import RetrievalEngine
from kaolalabot.memory.consolidation import (
    DecayAndArchive,
    ConsolidationEngine,
    ReconsolidationEngine,
)
from kaolalabot.memory.procedures import ProcedureExtractor, ProcedureUpdater

__all__ = [
    "Memory",
    "WorkingMemory",
    "EpisodicMemory",
    "SemanticMemory",
    "MemoryItem",
    "MemoryType",
    "InputCategory",
    "ContentSource",
    "PrivacyLevel",
    "MetaInfo",
    "ProceduralInfo",
    "SensoryBuffer",
    "RetrievalResult",
    "IngestionCandidate",
    "TaskLog",
    "MemoryLevel",
    "MemoryPriority",
    "MemoryManagerV2",
    "IngestionGate",
    "SensoryBufferManager",
    "RetrievalEngine",
    "DecayAndArchive",
    "ConsolidationEngine",
    "ReconsolidationEngine",
    "ProcedureExtractor",
    "ProcedureUpdater",
]
