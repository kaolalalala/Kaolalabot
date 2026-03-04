"""User profile system for personalized services."""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class UserPreference:
    """User preference data."""
    key: str
    value: Any
    confidence: float = 1.0
    updated_at: float = field(default_factory=time.time)


@dataclass
class UserProfile:
    """User profile with characteristics and preferences."""
    user_id: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    session_count: int = 0
    total_tokens: int = 0
    preferred_language: str = "zh-CN"
    communication_style: str = "friendly"
    interests: list[str] = field(default_factory=list)
    preferences: dict[str, UserPreference] = field(default_factory=dict)
    usage_stats: dict[str, int] = field(default_factory=dict)
    satisfaction_score: float | None = None


class UserProfileManager:
    """
    User profile manager for collecting and managing user data.
    
    Collects user characteristics, preferences, and usage patterns
    to provide personalized services.
    """

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path(".")
        self._profiles: dict[str, UserProfile] = {}
        self._load_profiles()

    def _get_profile_path(self, user_id: str) -> Path:
        """Get the file path for a user profile."""
        safe_id = user_id.replace("/", "_").replace(":", "_")
        return self.workspace / "user_profiles" / f"{safe_id}.json"

    def _load_profiles(self) -> None:
        """Load existing user profiles."""
        profiles_dir = self.workspace / "user_profiles"
        if not profiles_dir.exists():
            return
        
        for profile_file in profiles_dir.glob("*.json"):
            try:
                with open(profile_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    user_id = data.get("user_id", profile_file.stem)
                    self._profiles[user_id] = UserProfile(
                        user_id=user_id,
                        created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
                        updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
                        message_count=data.get("message_count", 0),
                        session_count=data.get("session_count", 0),
                        total_tokens=data.get("total_tokens", 0),
                        preferred_language=data.get("preferred_language", "zh-CN"),
                        communication_style=data.get("communication_style", "friendly"),
                        interests=data.get("interests", []),
                        preferences={
                            k: UserPreference(
                                key=v["key"],
                                value=v["value"],
                                confidence=v.get("confidence", 1.0),
                                updated_at=v.get("updated_at", time.time()),
                            )
                            for k, v in data.get("preferences", {}).items()
                        },
                        usage_stats=data.get("usage_stats", {}),
                        satisfaction_score=data.get("satisfaction_score"),
                    )
            except Exception as e:
                logger.warning(f"Failed to load profile {profile_file}: {e}")

    def _save_profile(self, profile: UserProfile) -> None:
        """Save a user profile to disk."""
        profiles_dir = self.workspace / "user_profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)

        profile_path = self._get_profile_path(profile.user_id)
        data = {
            "user_id": profile.user_id,
            "created_at": profile.created_at.isoformat(),
            "updated_at": datetime.now().isoformat(),
            "message_count": profile.message_count,
            "session_count": profile.session_count,
            "total_tokens": profile.total_tokens,
            "preferred_language": profile.preferred_language,
            "communication_style": profile.communication_style,
            "interests": profile.interests,
            "preferences": {
                k: {
                    "key": v.key,
                    "value": v.value,
                    "confidence": v.confidence,
                    "updated_at": v.updated_at,
                }
                for k, v in profile.preferences.items()
            },
            "usage_stats": profile.usage_stats,
            "satisfaction_score": profile.satisfaction_score,
        }

        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_or_create_profile(self, user_id: str) -> UserProfile:
        """Get or create a user profile."""
        if user_id not in self._profiles:
            self._profiles[user_id] = UserProfile(user_id=user_id)
        return self._profiles[user_id]

    def record_message(self, user_id: str) -> None:
        """Record a message from user."""
        profile = self.get_or_create_profile(user_id)
        profile.message_count += 1
        profile.updated_at = datetime.now()
        self._save_profile(profile)

    def record_session(self, user_id: str) -> None:
        """Record a new session for user."""
        profile = self.get_or_create_profile(user_id)
        profile.session_count += 1
        profile.updated_at = datetime.now()
        self._save_profile(profile)

    def update_preference(
        self,
        user_id: str,
        key: str,
        value: Any,
        confidence: float = 1.0,
    ) -> None:
        """Update a user preference."""
        profile = self.get_or_create_profile(user_id)
        
        existing = profile.preferences.get(key)
        if existing and existing.confidence > confidence:
            return
        
        profile.preferences[key] = UserPreference(
            key=key,
            value=value,
            confidence=confidence,
        )
        profile.updated_at = datetime.now()
        self._save_profile(profile)

    def add_interest(self, user_id: str, interest: str) -> None:
        """Add an interest to user profile."""
        profile = self.get_or_create_profile(user_id)
        
        if interest not in profile.interests:
            profile.interests.append(interest)
            profile.updated_at = datetime.now()
            self._save_profile(profile)

    def record_usage(
        self,
        user_id: str,
        feature: str,
        tokens: int = 0,
    ) -> None:
        """Record feature usage."""
        profile = self.get_or_create_profile(user_id)
        
        profile.usage_stats[feature] = profile.usage_stats.get(feature, 0) + 1
        profile.total_tokens += tokens
        profile.updated_at = datetime.now()
        self._save_profile(profile)

    def set_satisfaction(self, user_id: str, score: float) -> None:
        """Set user satisfaction score."""
        profile = self.get_or_create_profile(user_id)
        profile.satisfaction_score = score
        profile.updated_at = datetime.now()
        self._save_profile(profile)

    def get_personalization_context(self, user_id: str) -> dict[str, Any]:
        """Get personalization context for a user."""
        profile = self.get_or_create_profile(user_id)
        
        return {
            "preferred_language": profile.preferred_language,
            "communication_style": profile.communication_style,
            "interests": profile.interests,
            "preferences": {k: v.value for k, v in profile.preferences.items()},
            "message_count": profile.message_count,
            "session_count": profile.session_count,
            "satisfaction_score": profile.satisfaction_score,
        }

    def get_all_profiles(self) -> list[UserProfile]:
        """Get all user profiles."""
        return list(self._profiles.values())


class ProfileBasedResponseEnhancer:
    """
    Enhances responses based on user profiles.
    
    Uses user profile data to personalize responses.
    """

    def __init__(self, profile_manager: UserProfileManager):
        self.profile_manager = profile_manager

    def enhance_prompt(
        self,
        user_id: str,
        base_prompt: str,
    ) -> str:
        """Enhance prompt with user profile information."""
        context = self.profile_manager.get_personalization_context(user_id)
        
        enhancements = []
        
        if context.get("preferred_language"):
            enhancements.append(f"语言偏好: {context['preferred_language']}")
        
        if context.get("communication_style"):
            enhancements.append(f"沟通风格: {context['communication_style']}")
        
        if context.get("interests"):
            interests_str = ", ".join(context["interests"][:5])
            enhancements.append(f"兴趣: {interests_str}")
        
        if enhancements:
            return base_prompt + "\n\n用户画像: " + " | ".join(enhancements)
        
        return base_prompt
