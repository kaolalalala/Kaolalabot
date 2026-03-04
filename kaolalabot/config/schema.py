"""Configuration schema using Pydantic."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic_settings import BaseSettings


class Base(BaseModel):
    """Base model that accepts both camelCase and snake_case keys."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class FeishuConfig(Base):
    """Feishu/Lark channel configuration using WebSocket long connection."""

    enabled: bool = False
    app_id: str = ""
    app_secret: str = ""
    encrypt_key: str = ""
    verification_token: str = ""
    allow_from: list[str] = Field(default_factory=list)
    react_emoji: str = "THUMBSUP"


class DingTalkConfig(Base):
    """DingTalk channel configuration."""

    enabled: bool = False
    # Callback API used by DingTalk to deliver inbound events.
    callback_path: str = "/api/channels/dingtalk/callback"
    callback_host: str = "0.0.0.0"
    callback_port: int = 18791
    app_key: str = ""
    app_secret: str = ""
    robot_code: str = ""
    agent_id: str = ""
    # Outbound robot webhook mode (fallback/simple send path).
    webhook_access_token: str = ""
    webhook_secret: str = ""
    # Retry and health settings.
    reconnect_interval_seconds: int = 5
    max_retries: int = 3
    health_check_interval_seconds: int = 30
    allow_from: list[str] = Field(default_factory=list)


class ChannelsConfig(Base):
    """Configuration for chat channels."""

    send_progress: bool = True
    send_tool_hints: bool = False
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    dingtalk: DingTalkConfig = Field(default_factory=DingTalkConfig)
    voice: "VoiceChannelConfig | None" = Field(default_factory=lambda: VoiceChannelConfig())


class VoiceChannelConfig(BaseModel):
    """Configuration for voice channel."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    sample_rate: int = 16000
    vad_aggressiveness: int = 1
    vad_min_silence_duration_ms: int = 5000
    vad_energy_threshold: float = 500.0
    asr_model_size: str = "tiny"
    asr_device: str = "auto"
    tts_voice: str = "zh-CN-XiaoxiaoNeural"


class AgentDefaults(Base):
    """Default agent configuration."""

    workspace: str = "~/.kaolalabot/workspace"
    model: str = "anthropic/claude-sonnet-4-5"
    provider: str = "auto"
    max_tokens: int = 8192
    temperature: float = 0.1
    max_tool_iterations: int = 40
    memory_window: int = 100
    reasoning_effort: str | None = None


class AgentsConfig(Base):
    """Agent configuration."""

    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class ProviderConfig(Base):
    """LLM provider configuration."""

    api_key: str = ""
    api_base: str | None = None
    extra_headers: dict[str, str] | None = None
    fallback_priority: int = 0
    enabled: bool = True


class ProvidersConfig(Base):
    """Configuration for LLM providers."""

    custom: ProviderConfig = Field(default_factory=ProviderConfig)
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)
    enable_fallback: bool = True
    failover_timeout: float = 10.0
    health_check_interval: float = 30.0
    failure_threshold: int = 3


class GatewayConfig(Base):
    """Gateway/server configuration."""

    host: str = "0.0.0.0"
    port: int = 18790


class WebSearchConfig(Base):
    """Web search tool configuration."""

    api_key: str = ""
    max_results: int = 5


class WebToolsConfig(Base):
    """Web tools configuration."""

    proxy: str | None = None
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ExecToolConfig(Base):
    """Shell exec tool configuration."""

    timeout: int = 60
    path_append: str = ""
    backend: Literal["native", "openclaw"] = "native"
    openclaw_gateway_url: str = "http://127.0.0.1:18789"
    openclaw_token: str = ""
    openclaw_session_key: str = "main"
    openclaw_host: str = "sandbox"
    openclaw_security: str = "allowlist"
    openclaw_ask: str = "on-miss"
    openclaw_node: str = ""
    openclaw_elevated: bool = False


class PlaywrightToolConfig(Base):
    """Playwright browser automation tool configuration."""

    enabled: bool = True
    backend: Literal["native", "openclaw"] = "native"
    timeout_seconds: int = 30
    headless: bool = True
    channel: str = "msedge"
    screenshot_dir: str = "workspace/artifacts/playwright"
    openclaw_gateway_url: str = "http://127.0.0.1:18789"
    openclaw_token: str = ""
    openclaw_session_key: str = "main"
    openclaw_tool: str = "playwright"
    openclaw_host: str = "sandbox"
    openclaw_security: str = "allowlist"
    openclaw_ask: str = "on-miss"
    openclaw_node: str = ""
    openclaw_elevated: bool = False


class OpenClawBrowserToolConfig(Base):
    """OpenClaw dedicated browser tool configuration."""

    enabled: bool = False
    gateway_url: str = "http://127.0.0.1:18789"
    token: str = ""
    session_key: str = "main"
    profile: str = "openclaw"
    target: Literal["host", "node", "sandbox"] = "host"
    node: str = ""
    timeout_ms: int = 15000


class KaolaBrowserToolConfig(Base):
    """Kaolalabot dedicated browser tool configuration."""

    enabled: bool = True
    headless: bool = False
    channel: str = "msedge"
    timeout_ms: int = 45000


class ToolsConfig(Base):
    """Tools configuration."""

    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    playwright: PlaywrightToolConfig = Field(default_factory=PlaywrightToolConfig)
    kaola_browser: KaolaBrowserToolConfig = Field(default_factory=KaolaBrowserToolConfig)
    openclaw_browser: OpenClawBrowserToolConfig = Field(default_factory=OpenClawBrowserToolConfig)
    react_mode_enabled: bool = True
    react_observation_enabled: bool = True
    restrict_to_workspace: bool = False
    native_commands_enabled: bool = True
    native_deny_commands: list[str] = Field(default_factory=list)
    parallel_execution: bool = True
    max_parallel_workers: int = 4
    tool_timeout: float = 60.0


class CodingPlanConfig(Base):
    """Coding plan configuration - defines agent behavior patterns for coding tasks."""

    enabled: bool = False
    auto_plan: bool = True
    auto_review: bool = True
    max_planning_iterations: int = 3
    include_tests: bool = True
    strict_types: bool = False
    documentation_level: str = "standard"
    design_patterns: list[str] = Field(default_factory=lambda: ["solid", "dry"])


class RateLimitConfig(Base):
    """Rate limiting configuration."""

    enabled: bool = True
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10
    strategy: str = "token_bucket"


class VoiceConfig(Base):
    """Voice interaction configuration."""

    enabled: bool = False
    sample_rate: int = 16000
    frame_duration_ms: int = 20
    channels: int = 1
    vad_aggressiveness: int = 3
    vad_enabled: bool = True
    vad_min_speech_duration_ms: int = 250
    vad_min_silence_duration_ms: int = 5000
    vad_speech_timeout_ms: int = 3000
    vad_energy_threshold: float = 500.0
    asr_provider: str = "whisper"
    asr_model_size: str = "tiny"
    asr_language: str = "auto"
    asr_device: str = "auto"
    asr_window_interval_ms: int = 500
    asr_final_silence_ms: int = 1000
    tts_provider: str = "edge"
    tts_voice: str = "zh-CN-XiaoxiaoNeural"
    tts_rate: str = "+0%"
    tts_pitch: str = "+0Hz"
    tts_volume: str = "+0%"
    tts_max_chars_per_chunk: int = 50
    tts_chunk_interval_ms: int = 800
    turn_manager_enabled: bool = True
    turn_manager_barge_in: bool = True
    fsm_idle_timeout: float = 300.0
    fsm_thinking_timeout: float = 60.0
    fsm_speaking_timeout: float = 120.0


class MCPConfig(Base):
    """Minecraft MCP bridge configuration."""

    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 25575
    reconnect_interval_seconds: int = 5
    command_timeout_seconds: int = 10


class SchedulerConfig(Base):
    """Task scheduler configuration."""

    enabled: bool = False
    tick_seconds: float = 1.0
    max_concurrent_runs: int = 4
    storage_file: str = "workspace/system/tasks.json"
    log_file: str = "workspace/system/task_logs.jsonl"


class HeartbeatConfig(Base):
    """Heartbeat configuration."""

    enabled: bool = False
    endpoint: str = ""
    interval_seconds: int = 30
    timeout_seconds: int = 10
    max_failures_before_alert: int = 3
    auto_restart_on_failure: bool = False
    include_resource_usage: bool = True


class ClawhubConfig(Base):
    """Clawhub skills integration configuration."""

    enabled: bool = False
    base_url: str = ""
    api_token: str = ""
    sync_interval_seconds: int = 300
    skills_dir: str = "workspace/skills/clawhub"
    metadata_file: str = "workspace/skills/clawhub/index.json"


class OpenClawLocalConfig(Base):
    """OpenClaw local gateway integration."""

    enabled: bool = False
    gateway_url: str = "http://127.0.0.1:18789"
    token: str = ""
    timeout_seconds: int = 15
    session_key: str = "main"


class Config(BaseSettings):
    """Root configuration for kaolalabot."""

    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    coding_plan: CodingPlanConfig = Field(default_factory=CodingPlanConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)
    clawhub: ClawhubConfig = Field(default_factory=ClawhubConfig)
    openclaw: OpenClawLocalConfig = Field(default_factory=OpenClawLocalConfig)

    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        local_workspace = Path("D:/ai/kaolalabot/workspace")
        if local_workspace.exists():
            return local_workspace
        return Path(self.agents.defaults.workspace).expanduser()

    def get_provider(self, model: str | None = None) -> ProviderConfig | None:
        """Get matched provider config."""
        from kaolalabot.providers.registry import PROVIDERS

        forced = self.agents.defaults.provider
        if forced != "auto":
            p = getattr(self.providers, forced, None)
            return p if p else None

        model_lower = (model or self.agents.defaults.model).lower()
        model_normalized = model_lower.replace("-", "_")
        model_prefix = model_lower.split("/", 1)[0] if "/" in model_lower else ""
        normalized_prefix = model_prefix.replace("-", "_")

        def _kw_matches(kw: str) -> bool:
            kw = kw.lower()
            return kw in model_lower or kw.replace("-", "_") in model_normalized

        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and any(_kw_matches(kw) for kw in spec.keywords):
                if p.api_key:
                    return p

        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and p.api_key:
                return p
        return None

    def get_provider_name(self, model: str | None = None) -> str | None:
        """Get the registry name of the matched provider."""
        from kaolalabot.providers.registry import PROVIDERS

        forced = self.agents.defaults.provider
        if forced != "auto":
            p = getattr(self.providers, forced, None)
            return forced if p else None

        model_lower = (model or self.agents.defaults.model).lower()
        model_normalized = model_lower.replace("-", "_")

        def _kw_matches(kw: str) -> bool:
            kw = kw.lower()
            return kw in model_lower or kw.replace("-", "_") in model_normalized

        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and any(_kw_matches(kw) for kw in spec.keywords):
                if p.api_key:
                    return spec.name

        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and p.api_key:
                return spec.name
        return None

    def get_api_key(self, model: str | None = None) -> str | None:
        """Get API key for the given model."""
        p = self.get_provider(model)
        return p.api_key if p else None

    def get_api_base(self, model: str | None = None) -> str | None:
        """Get API base URL for the given model."""
        from kaolalabot.providers.registry import find_by_name

        p, name = self._match_provider(model)
        if p and p.api_base:
            return p.api_base
        if name:
            spec = find_by_name(name)
            if spec and spec.is_gateway and spec.default_api_base:
                return spec.default_api_base
        return None

    def _match_provider(self, model: str | None = None) -> tuple[ProviderConfig | None, str | None]:
        """Match provider config and its registry name."""
        from kaolalabot.providers.registry import PROVIDERS

        forced = self.agents.defaults.provider
        if forced != "auto":
            p = getattr(self.providers, forced, None)
            return (p, forced) if p else (None, None)

        model_lower = (model or self.agents.defaults.model).lower()
        model_normalized = model_lower.replace("-", "_")
        model_prefix = model_lower.split("/", 1)[0] if "/" in model_lower else ""
        normalized_prefix = model_prefix.replace("-", "_")

        def _kw_matches(kw: str) -> bool:
            kw = kw.lower()
            return kw in model_lower or kw.replace("-", "_") in model_normalized

        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and model_prefix and normalized_prefix == spec.name:
                if p.api_key:
                    return p, spec.name

        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and any(_kw_matches(kw) for kw in spec.keywords):
                if p.api_key:
                    return p, spec.name

        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and p.api_key:
                return p, spec.name
        return None, None

    model_config = ConfigDict(env_prefix="KAOLALABOT_", env_nested_delimiter="__")
