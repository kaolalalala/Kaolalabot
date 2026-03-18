"""Kaolalabot server configuration module - with Gateway support."""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    """Gateway configuration."""
    
    host: str = "0.0.0.0"
    port: int = 8000
    
    auth_mode: str = "token"
    auth_token: str = ""
    auth_password: str = ""
    
    remote_mode: str = "disabled"
    remote_url: str = ""
    remote_token: str = ""
    remote_password: str = ""
    
    session_timeout: int = 30
    max_sessions: int = 100


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_prefix="KAOLALABOT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    
    workspace_path: Path = Field(default=Path(__file__).resolve().parent.parent / "workspace")
    
    memory_working_capacity: int = 20
    memory_episodic_retention_days: int = 30
    memory_semantic_persist_dir: str = str(Path(__file__).resolve().parent.parent / "workspace" / "memory" / "chroma")
    
    cot_max_iterations: int = 10
    cot_enable_reflection: bool = True
    cot_streaming: bool = True
    
    llm_provider: str = "auto"
    llm_model: str = "deepseek/deepseek-coder"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096
    
    @property
    def workspace_path_expanded(self) -> Path:
        if self.workspace_path.exists():
            return self.workspace_path
        local_workspace = Path(__file__).resolve().parent.parent / "workspace"
        if local_workspace.exists():
            return local_workspace
        return self.workspace_path.expanduser()


gateway_settings = GatewaySettings()
settings = Settings()
