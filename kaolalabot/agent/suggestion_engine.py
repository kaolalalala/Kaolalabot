"""Proactive suggestion engine for user behavior analysis and recommendations."""

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from loguru import logger


class SuggestionType(Enum):
    """Types of suggestions."""
    CONTEXTUAL = "contextual"
    FOLLOW_UP = "follow_up"
    FEATURE = "feature"
    PERSONALIZED = "personalized"


@dataclass
class Suggestion:
    """A suggestion to offer to the user."""
    id: str
    type: SuggestionType
    content: str
    trigger_reason: str
    priority: float = 0.5
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class UserBehavior:
    """User behavior data for analysis."""
    user_id: str
    message_count: int = 0
    session_count: int = 0
    last_seen: float = 0.0
    avg_turns_per_session: float = 0.0
    common_intents: dict[str, int] = field(default_factory=dict)
    feature_usage: dict[str, int] = field(default_factory=dict)
    time_distribution: dict[int, int] = field(default_factory=dict)
    satisfaction_trend: list[float] = field(default_factory=list)


class BehaviorAnalyzer:
    """
    User behavior analyzer.
    
    Analyzes user patterns and generates insights.
    """

    def __init__(self):
        self._behavior_cache: dict[str, UserBehavior] = {}

    def get_or_create_behavior(self, user_id: str) -> UserBehavior:
        """Get or create behavior data for a user."""
        if user_id not in self._behavior_cache:
            self._behavior_cache[user_id] = UserBehavior(
                user_id=user_id,
                last_seen=time.time(),
            )
        return self._behavior_cache[user_id]

    def record_message(self, user_id: str) -> None:
        """Record a message from user."""
        behavior = self.get_or_create_behavior(user_id)
        behavior.message_count += 1
        behavior.last_seen = time.time()
        
        hour = datetime.now().hour
        behavior.time_distribution[hour] = behavior.time_distribution.get(hour, 0) + 1

    def record_session(self, user_id: str, turn_count: int) -> None:
        """Record a session."""
        behavior = self.get_or_create_behavior(user_id)
        behavior.session_count += 1
        
        if behavior.avg_turns_per_session == 0:
            behavior.avg_turns_per_session = turn_count
        else:
            behavior.avg_turns_per_session = (
                (behavior.avg_turns_per_session * (behavior.session_count - 1) + turn_count)
                / behavior.session_count
            )

    def record_intent(self, user_id: str, intent: str) -> None:
        """Record an intent."""
        behavior = self.get_or_create_behavior(user_id)
        behavior.common_intents[intent] = behavior.common_intents.get(intent, 0) + 1

    def record_feature_usage(self, user_id: str, feature: str) -> None:
        """Record feature usage."""
        behavior = self.get_or_create_behavior(user_id)
        behavior.feature_usage[feature] = behavior.feature_usage.get(feature, 0) + 1

    def analyze_patterns(self, user_id: str) -> dict[str, Any]:
        """Analyze user patterns and return insights."""
        behavior = self.get_or_create_behavior(user_id)
        
        patterns = {}
        
        if behavior.time_distribution:
            peak_hour = max(behavior.time_distribution.items(), key=lambda x: x[1])[0]
            patterns["peak_hour"] = peak_hour
        
        if behavior.common_intents:
            top_intent = max(behavior.common_intents.items(), key=lambda x: x[1])[0]
            patterns["top_intent"] = top_intent
        
        if behavior.feature_usage:
            top_feature = max(behavior.feature_usage.items(), key=lambda x: x[1])[0]
            patterns["top_feature"] = top_feature
        
        patterns["engagement_level"] = self._calculate_engagement(behavior)
        
        return patterns

    def _calculate_engagement(self, behavior: UserBehavior) -> str:
        """Calculate user engagement level."""
        if behavior.message_count < 10:
            return "low"
        elif behavior.message_count < 50:
            return "medium"
        else:
            return "high"


class SuggestionGenerator:
    """
    Suggestion generator for proactive recommendations.
    
    Generates contextual and personalized suggestions based on
    user behavior and system state.
    """

    def __init__(self, behavior_analyzer: BehaviorAnalyzer):
        self.behavior_analyzer = behavior_analyzer
        self._suggestion_templates = self._init_templates()
        self._cooldowns: dict[str, float] = {}

    def _init_templates(self) -> dict[SuggestionType, list[str]]:
        """Initialize suggestion templates."""
        return {
            SuggestionType.CONTEXTUAL: [
                "我可以帮你搜索更多信息，你需要吗？",
                "你想让我解释一下刚才的回答吗？",
                "需要我继续帮你完成其他任务吗？",
            ],
            SuggestionType.FOLLOW_UP: [
                "你对这个话题还有其他问题吗？",
                "需要我进一步帮你吗？",
                "还有什么我可以帮你的？",
            ],
            SuggestionType.FEATURE: [
                "你可以直接让我执行本地任务，例如打开应用或运行命令",
                "你可以让我帮你搜索网络信息",
                "我可以帮你读取和写入文件",
            ],
            SuggestionType.PERSONALIZED: [
                "根据你的使用习惯，你可能对高级自动化功能感兴趣。",
                "你已多次使用该功能，需要我给你更高效的用法建议吗？",
            ],
        }

    async def generate_suggestions(
        self,
        user_id: str,
        current_context: dict[str, Any] | None = None,
        max_suggestions: int = 2,
    ) -> list[Suggestion]:
        """Generate suggestions for a user."""
        if self._is_in_cooldown(user_id):
            return []
        
        suggestions = []
        
        patterns = self.behavior_analyzer.analyze_patterns(user_id)
        
        if current_context:
            contextual = await self._generate_contextual(user_id, current_context)
            if contextual:
                suggestions.append(contextual)
        
        if patterns.get("engagement_level") == "high":
            personalized = await self._generate_personalized(user_id, patterns)
            if personalized:
                suggestions.append(personalized)
        
        follow_up = self._generate_follow_up(user_id)
        if follow_up and len(suggestions) < max_suggestions:
            suggestions.append(follow_up)
        
        feature_suggestion = self._generate_feature_suggestion(user_id)
        if feature_suggestion and len(suggestions) < max_suggestions:
            suggestions.append(feature_suggestion)
        
        suggestions.sort(key=lambda x: x.priority, reverse=True)
        
        return suggestions[:max_suggestions]

    async def _generate_contextual(
        self,
        user_id: str,
        context: dict[str, Any],
    ) -> Suggestion | None:
        """Generate contextual suggestion."""
        templates = self._suggestion_templates.get(SuggestionType.CONTEXTUAL, [])
        if not templates:
            return None
        
        content = templates[hash(user_id) % len(templates)]
        
        return Suggestion(
            id=f"suggestion:{time.time()}",
            type=SuggestionType.CONTEXTUAL,
            content=content,
            trigger_reason="contextual",
            priority=0.8,
            metadata=context,
        )

    async def _generate_personalized(
        self,
        user_id: str,
        patterns: dict[str, Any],
    ) -> Suggestion | None:
        """Generate personalized suggestion."""
        templates = self._suggestion_templates.get(SuggestionType.PERSONALIZED, [])
        if not templates:
            return None
        
        content = templates[hash(user_id) % len(templates)]
        
        return Suggestion(
            id=f"suggestion:{time.time()}",
            type=SuggestionType.PERSONALIZED,
            content=content,
            trigger_reason="personalized",
            priority=0.7,
            metadata=patterns,
        )

    def _generate_follow_up(self, user_id: str) -> Suggestion | None:
        """Generate follow-up suggestion."""
        templates = self._suggestion_templates.get(SuggestionType.FOLLOW_UP, [])
        if not templates:
            return None
        
        content = templates[hash(user_id) % len(templates)]
        
        return Suggestion(
            id=f"suggestion:{time.time()}",
            type=SuggestionType.FOLLOW_UP,
            content=content,
            trigger_reason="follow_up",
            priority=0.6,
        )

    def _generate_feature_suggestion(self, user_id: str) -> Suggestion | None:
        """Generate feature suggestion."""
        templates = self._suggestion_templates.get(SuggestionType.FEATURE, [])
        if not templates:
            return None
        
        behavior = self.behavior_analyzer.get_or_create_behavior(user_id)
        
        if behavior.message_count < 5:
            content = templates[0]
        else:
            content = templates[hash(user_id) % len(templates)]
        
        return Suggestion(
            id=f"suggestion:{time.time()}",
            type=SuggestionType.FEATURE,
            content=content,
            trigger_reason="feature_discovery",
            priority=0.4,
        )

    def _is_in_cooldown(self, user_id: str) -> bool:
        """Check if user is in suggestion cooldown."""
        if user_id in self._cooldowns:
            if time.time() - self._cooldowns[user_id] < 300:
                return True
        
        self._cooldowns[user_id] = time.time()
        return False

    async def record_suggestion_click(self, suggestion: Suggestion) -> None:
        """Record when user clicks a suggestion."""
        logger.info(f"Suggestion clicked: {suggestion.id} - {suggestion.content}")

