"""Kaolalabot configuration module."""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_prefix="KAOLALABOT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # Workspace settings
    workspace_path: Path = Field(default=Path("D:/ai/kaolalabot/workspace"))
    
    # Memory settings
    memory_working_capacity: int = 20
    memory_episodic_retention_days: int = 30
    memory_semantic_persist_dir: str = "D:/ai/kaolalabot/workspace/memory/chroma"
    
    # CoT settings
    cot_max_iterations: int = 10
    cot_enable_reflection: bool = True
    cot_streaming: bool = True
    
    # LLM settings
    llm_provider: str = "auto"
    llm_model: str = "deepseek/deepseek-chat"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096
    
    @property
    def workspace_path_expanded(self) -> Path:
        """Get expanded workspace path."""
        if self.workspace_path.exists():
            return self.workspace_path
        
        local_workspace = Path("D:/ai/kaolalabot/workspace")
        if local_workspace.exists():
            return local_workspace
        
        return self.workspace_path.expanduser()


settings = Settings()
