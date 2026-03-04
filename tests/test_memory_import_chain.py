from kaolalabot.memory.manager import MemoryManager
from kaolalabot.memory.models import EpisodicMemory, Memory, SemanticMemory, WorkingMemory


def test_memory_legacy_models_importable():
    assert Memory is not None
    assert WorkingMemory is not None
    assert EpisodicMemory is not None
    assert SemanticMemory is not None


def test_memory_manager_importable():
    assert MemoryManager is not None
