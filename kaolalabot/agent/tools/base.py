"""Base tool interface for agent tools."""

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """
    Abstract base class for agent tools.

    Each tool should implement this interface to be registered
    with the tool registry.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the tool name."""
        pass

    @property
    def description(self) -> str:
        """Get the tool description."""
        return ""

    @abstractmethod
    async def execute(self, **params: Any) -> str:
        """
        Execute the tool with given parameters.

        Args:
            **params: Tool parameters.

        Returns:
            Tool execution result as a string.
        """
        pass

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """
        Validate tool parameters.

        Args:
            params: Parameters to validate.

        Returns:
            List of validation error messages, empty if valid.
        """
        return []

    def to_schema(self) -> dict[str, Any]:
        """
        Convert tool to OpenAI function schema.

        Returns:
            OpenAI function definition dict.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        }
