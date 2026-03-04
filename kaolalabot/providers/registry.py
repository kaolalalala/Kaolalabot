"""Provider registry for LLM provider configuration."""

from dataclasses import dataclass, field


@dataclass
class ProviderSpec:
    """Specification for an LLM provider."""

    name: str
    label: str
    keywords: list[str] = field(default_factory=list)
    env_key: str | None = None
    litellm_prefix: str | None = None
    default_api_base: str | None = None
    is_gateway: bool = False
    is_oauth: bool = False
    is_local: bool = False
    strip_model_prefix: bool = False
    supports_prompt_caching: bool = False
    env_extras: list[tuple[str, str]] = field(default_factory=list)
    model_overrides: list[tuple[str, dict]] = field(default_factory=list)
    skip_prefixes: list[str] = field(default_factory=list)


PROVIDERS = [
    ProviderSpec(
        name="openrouter",
        label="OpenRouter",
        keywords=["openrouter"],
        env_key="OPENROUTER_API_KEY",
        litellm_prefix="openrouter",
        default_api_base="https://openrouter.ai/api/v1",
        is_gateway=True,
        supports_prompt_caching=True,
    ),
    ProviderSpec(
        name="anthropic",
        label="Anthropic",
        keywords=["anthropic", "claude"],
        env_key="ANTHROPIC_API_KEY",
        litellm_prefix="anthropic",
        supports_prompt_caching=True,
    ),
    ProviderSpec(
        name="openai",
        label="OpenAI",
        keywords=["openai", "gpt-", "o1-", "o3-", "gpt4", "gpt-4", "gpt-5", "chatgpt"],
        env_key="OPENAI_API_KEY",
        litellm_prefix="openai",
        skip_prefixes=["openrouter/", "anthropic/"],
    ),
    ProviderSpec(
        name="deepseek",
        label="DeepSeek",
        keywords=["deepseek"],
        env_key="DEEPSEEK_API_KEY",
        litellm_prefix="deepseek",
        default_api_base="https://api.deepseek.com/v1",
    ),
    ProviderSpec(
        name="groq",
        label="Groq",
        keywords=["groq"],
        env_key="GROQ_API_KEY",
        litellm_prefix="groq",
    ),
    ProviderSpec(
        name="zhipu",
        label="ZhipuAI",
        keywords=["zhipu", "glm-"],
        env_key="ZHIPU_API_KEY",
        litellm_prefix="zhipu",
    ),
    ProviderSpec(
        name="dashscope",
        label="DashScope",
        keywords=["dashscope", "qwen", "tongyi"],
        env_key="DASHSCOPE_API_KEY",
        litellm_prefix="dashscope",
    ),
    ProviderSpec(
        name="moonshot",
        label="Moonshot",
        keywords=["moonshot", "kimi"],
        env_key="MOONSHOT_API_KEY",
        litellm_prefix="moonshot",
        default_api_base="https://api.moonshot.cn/v1",
    ),
    ProviderSpec(
        name="custom",
        label="Custom",
        keywords=[],
        is_local=True,
    ),
]


def find_by_name(name: str) -> ProviderSpec | None:
    """Find a provider spec by its registry name."""
    for spec in PROVIDERS:
        if spec.name == name:
            return spec
    return None


def find_by_model(model: str) -> ProviderSpec | None:
    """Find a provider spec by model name keywords."""
    model_lower = model.lower()
    model_normalized = model_lower.replace("-", "_")

    def _kw_matches(kw: str) -> bool:
        kw = kw.lower()
        return kw in model_lower or kw.replace("-", "_") in model_normalized

    for spec in PROVIDERS:
        if any(_kw_matches(kw) for kw in spec.keywords):
            return spec
    return None


def find_gateway(provider_name: str | None, api_key: str | None, api_base: str | None) -> ProviderSpec | None:
    """Detect if this is a gateway/local deployment."""
    if provider_name:
        spec = find_by_name(provider_name)
        if spec and (spec.is_gateway or spec.is_local):
            return spec

    if api_base and api_key:
        return find_by_name("custom")

    return None
