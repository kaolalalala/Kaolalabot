"""Intent classification system with confidence scoring."""

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


class IntentCategory(Enum):
    """Primary intent categories."""
    QUESTION = "question"
    TASK = "task"
    CHAT = "chat"
    COMMAND = "command"
    FEEDBACK = "feedback"
    CLARIFICATION = "clarification"
    GREETING = "greeting"
    GOODBYE = "goodbye"
    UNKNOWN = "unknown"


@dataclass
class Intent:
    """Classified intent with confidence score."""
    category: IntentCategory
    confidence: float
    sub_intent: str | None = None
    entities: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


@dataclass
class ClassificationResult:
    """Result of intent classification."""
    primary_intent: Intent
    alternative_intents: list[Intent] = field(default_factory=list)
    context_enhanced: bool = False
    requires_clarification: bool = False


class IntentClassifier:
    """
    Intent classifier with confidence scoring.
    
    Uses pattern matching and keyword analysis for initial classification,
    with context enhancement for improved accuracy.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.7,
        enable_ml_enhancement: bool = False,
    ):
        self.confidence_threshold = confidence_threshold
        self.enable_ml_enhancement = enable_ml_enhancement
        
        self._patterns = self._init_patterns()
        self._keywords = self._init_keywords()
        self._classify_history: list[dict[str, Any]] = []

    def _init_patterns(self) -> dict[IntentCategory, list[re.Pattern]]:
        """Initialize regex patterns for intent detection."""
        return {
            IntentCategory.COMMAND: [
                re.compile(r"^(/[\w]+)"),
                re.compile(r"^(帮?我|请|能不能|能不能够)", re.IGNORECASE),
            ],
            IntentCategory.QUESTION: [
                re.compile(r"^(什么|哪|怎么|如何|为什么|多少|几|是不是|有没有|能不能)", re.IGNORECASE),
                re.compile(r"\?$"),
            ],
            IntentCategory.TASK: [
                re.compile(r"^(搜索|查找|查询|获取|下载|上传|创建|删除|修改|更新|执行)", re.IGNORECASE),
            ],
            IntentCategory.GREETING: [
                re.compile(r"^(你好|您好|嗨|hi|hello|hey|早上好|下午好|晚上好)", re.IGNORECASE),
            ],
            IntentCategory.GOODBYE: [
                re.compile(r"^(再见|拜拜|bye|goodbye|下次见|再会)", re.IGNORECASE),
            ],
            IntentCategory.FEEDBACK: [
                re.compile(r"^(谢谢|感谢|不错|很好|太棒了|真棒|满意|不满意)", re.IGNORECASE),
            ],
        }

    def _init_keywords(self) -> dict[IntentCategory, list[str]]:
        """Initialize keyword lists for intent detection."""
        return {
            IntentCategory.QUESTION: [
                "什么", "哪", "怎么", "如何", "为什么", "多少", "几", "是不是", "有没有",
                "能否", "请问", "想知道", "问", "?", 
            ],
            IntentCategory.TASK: [
                "搜索", "查找", "查询", "获取", "下载", "上传", "创建", "删除", 
                "修改", "更新", "执行", "完成", "做", "帮我", "请帮我",
            ],
            IntentCategory.CHAT: [
                "聊聊", "聊天", "说话", "对话", "谈", "说",
            ],
            IntentCategory.COMMAND: [
                "/new", "/help", "/deep", "/status", "/clear",
            ],
            IntentCategory.FEEDBACK: [
                "谢谢", "感谢", "不错", "很好", "太棒了", "真棒", "满意", "不满意",
                "喜欢", "讨厌", "好", "不好",
            ],
            IntentCategory.GREETING: [
                "你好", "您好", "嗨", "hi", "hello", "hey", "早上好", "下午好", "晚上好",
                "初次见面", "久仰",
            ],
            IntentCategory.GOODBYE: [
                "再见", "拜拜", "bye", "goodbye", "下次见", "再会", "走了", "下线",
            ],
        }

    def classify(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> ClassificationResult:
        """
        Classify user intent from text.
        
        Args:
            text: User input text
            context: Optional context from previous messages
            
        Returns:
            ClassificationResult with primary and alternative intents
        """
        text = text.strip()
        
        scores = self._calculate_intent_scores(text, context)
        
        sorted_intents = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        primary_category, primary_confidence = sorted_intents[0]
        
        primary_intent = Intent(
            category=primary_category,
            confidence=primary_confidence,
            entities=self._extract_entities(text, primary_category),
            raw_text=text,
        )
        
        alternative_intents = []
        for category, score in sorted_intents[1:4]:
            if score > 0.1:
                alternative_intents.append(Intent(
                    category=category,
                    confidence=score,
                    raw_text=text,
                ))
        
        requires_clarification = primary_confidence < self.confidence_threshold
        
        self._classify_history.append({
            "text": text,
            "primary": primary_category.value,
            "confidence": primary_confidence,
            "timestamp": time.time(),
        })
        
        if len(self._classify_history) > 100:
            self._classify_history = self._classify_history[-100:]
        
        return ClassificationResult(
            primary_intent=primary_intent,
            alternative_intents=alternative_intents,
            context_enhanced=context is not None,
            requires_clarification=requires_clarification,
        )

    def _calculate_intent_scores(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> dict[IntentCategory, float]:
        """Calculate intent scores based on patterns and keywords."""
        scores = {cat: 0.0 for cat in IntentCategory}
        
        text_lower = text.lower()
        
        for category, patterns in self._patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    scores[category] += 0.4
                    break
        
        for category, keywords in self._keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    scores[category] += 0.2
        
        if context:
            scores = self._enhance_with_context(scores, text, context)
        
        if scores[IntentCategory.COMMAND] > 0:
            scores[IntentCategory.COMMAND] = max(scores[IntentCategory.COMMAND], 0.8)
        
        total = sum(scores.values())
        if total > 0:
            for cat in scores:
                scores[cat] = scores[cat] / total
        
        return scores

    def _enhance_with_context(
        self,
        scores: dict[IntentCategory, float],
        text: str,
        context: dict[str, Any],
    ) -> dict[IntentCategory, float]:
        """Enhance scores using conversation context."""
        last_intent = context.get("last_intent")
        if last_intent:
            if last_intent == IntentCategory.QUESTION.value:
                if any(q in text for q in ["是的", "对", "好", "明白"]):
                    scores[IntentCategory.CLARIFICATION] = 0.8
                    scores[IntentCategory.TASK] = 0.6
            elif last_intent == IntentCategory.TASK.value:
                if any(q in text for q in ["好了", "完成", "结束了", "成功"]):
                    scores[IntentCategory.FEEDBACK] = 0.5
        
        turn_count = context.get("turn_count", 0)
        if turn_count == 0:
            scores[IntentCategory.GREETING] += 0.2
        
        return scores

    def _extract_entities(
        self,
        text: str,
        category: IntentCategory,
    ) -> dict[str, Any]:
        """Extract entities from text based on category."""
        entities = {}
        
        url_pattern = re.compile(r"https?://[^\s]+")
        urls = url_pattern.findall(text)
        if urls:
            entities["urls"] = urls
        
        file_pattern = re.compile(r"[\w-]+\.[\w]+")
        files = file_pattern.findall(text)
        if files:
            entities["files"] = files
        
        return entities

    def get_intent_distribution(self) -> dict[str, int]:
        """Get distribution of classified intents."""
        distribution = {cat.value: 0 for cat in IntentCategory}
        
        for record in self._classify_history:
            intent = record["primary"]
            if intent in distribution:
                distribution[intent] += 1
        
        return distribution


class AdaptiveIntentClassifier(IntentClassifier):
    """
    Adaptive intent classifier that learns from feedback.
    
    Improves accuracy over time based on user corrections and
    successful classifications.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._feedback_data: list[dict[str, Any]] = []
        self._corrections: dict[str, str] = {}

    def record_feedback(
        self,
        text: str,
        classified_intent: str,
        correct_intent: str | None = None,
        was_successful: bool = True,
    ) -> None:
        """Record feedback for classification accuracy improvement."""
        self._feedback_data.append({
            "text": text,
            "classified": classified_intent,
            "correct": correct_intent,
            "successful": was_successful,
            "timestamp": time.time(),
        })
        
        if correct_intent and correct_intent != classified_intent:
            key = text[:50].lower()
            self._corrections[key] = correct_intent
        
        if len(self._feedback_data) > 500:
            self._feedback_data = self._feedback_data[-500:]

    def get_accuracy_stats(self) -> dict[str, Any]:
        """Get classification accuracy statistics."""
        if not self._feedback_data:
            return {"total": 0, "accuracy": 0.0}
        
        total = len(self._feedback_data)
        successful = sum(1 for f in self._feedback_data if f["successful"])
        
        return {
            "total": total,
            "successful": successful,
            "accuracy": successful / total if total > 0 else 0.0,
            "corrections": len(self._corrections),
        }
