"""Ingestion Gate - Controls what gets stored in long-term memory."""

import re
from datetime import datetime
from typing import Optional

from loguru import logger

from kaolalabot.memory.models import (
    MemoryItem, MemoryType, InputCategory, ContentSource,
    MetaInfo, IngestionCandidate, SensoryBuffer
)


class IngestionGate:
    """
    写入门控 - 决定输入是否进入长期记忆系统
    
    职责:
    1. 输入分类
    2. 写入判定
    3. 路由规则
    """

    FACT_KEYWORDS = [
        "是", "位于", "等于", "叫做", "称为", "is", "located", "equals", "called",
        "叫做", "名字是", "email", "电话", "地址", "偏好", "喜欢", "讨厌",
        "记住", "remember", "always", "never", "must", "should"
    ]

    EVENT_KEYWORDS = [
        "做了", "完成", "调用", "执行", "发生", "did", "completed", "executed",
        "called", "returned", "received", "sent", "wrote", "read"
    ]

    SKILL_KEYWORDS = [
        "如何", "怎么", "方法", "步骤", "流程", "how to", "steps", "process",
        "修复", "解决", "问题", "故障", "fix", "solve", "troubleshoot",
        "成功", "失败", "经验", "技巧", "skill", "technique", "经验是"
    ]

    TEMP_KEYWORDS = [
        "当前", "现在", "这里", "这个", "那个", "当前任务", "当前目标",
        "current", "now", "here", "this", "temporary", "pending"
    ]

    SPECULATION_KEYWORDS = [
        "可能", "也许", "大概", "估计", "猜测", "maybe", "perhaps", "probably",
        "might", "could be", "应该", "似乎", "看起来"
    ]

    NOISE_PATTERNS = [
        r"^(hi|hello|hey|你好|您好|嗨)$",
        r"^(ok|okay|好|知道了|嗯|yes|no)$",
        r"^[\s]*$",
        r"^(哈哈|呵呵|嘿嘿|么么哒|表情).*$",
        r"^[^a-zA-Z\u4e00-\u9fff]*$",
    ]

    PERSISTENT_INDICATORS = [
        "记住", "记住这个", "以后", "将来", "每次", "总是", "永远",
        "remember", "always", "future", "later", "persist"
    ]

    def __init__(self):
        self.noise_re = [re.compile(p, re.IGNORECASE) for p in self.NOISE_PATTERNS]
        logger.info("IngestionGate initialized")

    def classify(self, content: str, source: ContentSource = ContentSource.USER_INPUT) -> IngestionCandidate:
        """
        对输入进行分类
        
        Args:
            content: 待分类内容
            source: 内容来源
            
        Returns:
            IngestionCandidate: 带分类信息的候选记忆
        """
        content_clean = content.strip()
        
        category = self._determine_category(content_clean)
        
        raw_score = self._calculate_raw_score(content_clean, category)
        
        suggested_type = self._route_to_memory_type(category, content_clean)
        
        entities = self._extract_entities(content_clean)
        
        relations = self._extract_relations(content_clean, entities)
        
        candidate = IngestionCandidate(
            content=content_clean,
            category=category,
            source=source,
            raw_score=raw_score,
            suggested_type=suggested_type,
            entities=entities,
            relations=relations,
        )
        
        logger.debug(f"Classified content as {category.value}, suggested type: {suggested_type}")
        return candidate

    def _determine_category(self, content: str) -> InputCategory:
        """确定输入类别"""
        content_lower = content.lower()
        
        for pattern in self.noise_re:
            if pattern.match(content):
                return InputCategory.NOISE
        
        fact_score = sum(1 for kw in self.FACT_KEYWORDS if kw.lower() in content_lower)
        event_score = sum(1 for kw in self.EVENT_KEYWORDS if kw.lower() in content_lower)
        skill_score = sum(1 for kw in self.SKILL_KEYWORDS if kw.lower() in content_lower)
        temp_score = sum(1 for kw in self.TEMP_KEYWORDS if kw.lower() in content_lower)
        spec_score = sum(1 for kw in self.SPECULATION_KEYWORDS if kw.lower() in content_lower)
        
        scores = {
            InputCategory.FACT: fact_score,
            InputCategory.EVENT: event_score,
            InputCategory.SKILL_EXPERIENCE: skill_score,
            InputCategory.TEMP_STATE: temp_score,
            InputCategory.SPECULATION: spec_score,
        }
        
        max_score = max(scores.values())
        if max_score == 0:
            return InputCategory.NOISE
        
        for cat, score in scores.items():
            if score == max_score:
                return cat
        
        return InputCategory.NOISE

    def _calculate_raw_score(self, content: str, category: InputCategory) -> float:
        """计算原始分数"""
        score = 0.5
        
        if category == InputCategory.FACT:
            score += 0.2
        elif category == InputCategory.EVENT:
            score += 0.1
        elif category == InputCategory.SKILL_EXPERIENCE:
            score += 0.3
        elif category == InputCategory.TEMP_STATE:
            score -= 0.2
        elif category == InputCategory.SPECULATION:
            score -= 0.3
        elif category == InputCategory.NOISE:
            return 0.0
        
        for indicator in self.PERSISTENT_INDICATORS:
            if indicator.lower() in content.lower():
                score += 0.2
                break
        
        length = len(content)
        if 10 < length < 500:
            score += 0.1
        elif length > 1000:
            score -= 0.1
        
        return max(0.0, min(1.0, score))

    def _route_to_memory_type(self, category: InputCategory, content: str) -> MemoryType:
        """路由到合适的记忆类型"""
        content_lower = content.lower()
        
        if category == InputCategory.TEMP_STATE:
            return MemoryType.WORKING
        
        if category == InputCategory.EVENT:
            return MemoryType.EPISODIC
        
        if category == InputCategory.FACT:
            if any(kw in content_lower for kw in ["偏好", "喜欢", "讨厌", "preference", "like", "dislike"]):
                return MemoryType.SEMANTIC
            return MemoryType.SEMANTIC
        
        if category == InputCategory.SKILL_EXPERIENCE:
            return MemoryType.PROCEDURAL
        
        if category == InputCategory.SPECULATION:
            return MemoryType.SEMANTIC
        
        return MemoryType.WORKING

    def _extract_entities(self, content: str) -> list[str]:
        """提取实体"""
        entities = []
        
        mention_patterns = [
            r"@(\w+)",
            r"<@(\w+)>",
        ]
        
        for pattern in mention_patterns:
            matches = re.findall(pattern, content)
            entities.extend(matches)
        
        return list(set(entities))

    def _extract_relations(self, content: str, entities: list[str]) -> list[dict]:
        """提取关系"""
        relations = []
        
        action_verbs = ["调用", "使用", "创建", "读取", "写入", "删除", "call", "use", "create", "read", "write", "delete"]
        content_lower = content.lower()
        
        for verb in action_verbs:
            if verb in content_lower:
                relations.append({
                    "type": "action",
                    "verb": verb,
                })
                break
        
        return relations

    def should_store(self, candidate: IngestionCandidate) -> tuple[bool, str]:
        """
        判断是否应该存储
        
        Args:
            candidate: 记忆候选
            
        Returns:
            (是否允许, 原因)
        """
        if candidate.category == InputCategory.NOISE:
            return False, "noise_content"
        
        if candidate.raw_score < 0.3:
            return False, "low_score"
        
        if candidate.category == InputCategory.SPECULATION and candidate.raw_score < 0.6:
            return False, "uncertain_speculation"
        
        if candidate.suggested_type == MemoryType.WORKING and candidate.raw_score < 0.4:
            return False, "low_priority_working"
        
        return True, "approved"

    def create_memory_item(self, candidate: IngestionCandidate, session_id: Optional[str] = None) -> MemoryItem:
        """
        根据候选创建记忆项
        
        Args:
            candidate: 记忆候选
            session_id: 会话ID
            
        Returns:
            MemoryItem: 完整的记忆项
        """
        meta = MetaInfo(
            source=candidate.source,
            confidence=self._category_to_confidence(candidate.category),
            salience=candidate.raw_score,
            clarity=self._calculate_clarity(candidate.content),
        )
        
        memory = MemoryItem(
            type=candidate.suggested_type or MemoryType.WORKING,
            content_raw=candidate.content,
            summary=candidate.content[:200] if len(candidate.content) > 200 else candidate.content,
            entities=candidate.entities,
            relations=candidate.relations,
            meta=meta,
            session_id=session_id,
        )
        
        logger.info(f"Created memory item: type={memory.type.value}, confidence={meta.confidence}")
        return memory

    def _category_to_confidence(self, category: InputCategory) -> float:
        """根据类别设置置信度"""
        confidence_map = {
            InputCategory.FACT: 0.9,
            InputCategory.EVENT: 0.8,
            InputCategory.SKILL_EXPERIENCE: 0.7,
            InputCategory.TEMP_STATE: 0.5,
            InputCategory.SPECULATION: 0.3,
            InputCategory.NOISE: 0.0,
        }
        return confidence_map.get(category, 0.5)

    def _calculate_clarity(self, content: str) -> float:
        """计算内容清晰度"""
        clarity = 1.0
        
        vague_words = ["可能", "也许", "大概", "似乎", "maybe", "perhaps", "probably", "might"]
        for word in vague_words:
            if word in content.lower():
                clarity -= 0.1
        
        question_marks = content.count("?")
        if question_marks > 0:
            clarity -= question_marks * 0.05
        
        return max(0.1, min(1.0, clarity))


class SensoryBufferManager:
    """感官缓冲管理器"""
    
    def __init__(self, max_size: int = 50, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._buffer: list[SensoryBuffer] = []
    
    def add(self, content: str, source: ContentSource = ContentSource.USER_INPUT) -> SensoryBuffer:
        """添加原始输入到缓冲"""
        buffer_item = SensoryBuffer(
            content=content,
            source=source,
            created_at=datetime.now(),
        )
        
        self._buffer.append(buffer_item)
        
        if len(self._buffer) > self.max_size:
            self._buffer.pop(0)
        
        return buffer_item
    
    def get_unprocessed(self) -> list[SensoryBuffer]:
        """获取未处理的缓冲项"""
        now = datetime.now()
        cutoff = now.timestamp() - self.ttl_seconds
        
        unprocessed = []
        for item in self._buffer:
            if not item.processed and item.created_at.timestamp() > cutoff:
                unprocessed.append(item)
        
        return unprocessed
    
    def mark_processed(self, buffer_id: str) -> None:
        """标记为已处理"""
        for item in self._buffer:
            if item.id == buffer_id:
                item.processed = True
                break
    
    def clear(self) -> None:
        """清空缓冲"""
        self._buffer.clear()
