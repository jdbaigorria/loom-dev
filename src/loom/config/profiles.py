"""
loom.config.profiles — Opinionated presets (model / retry), referenced by name.

Instead of hardcoding opinions in library Python (the old ``retry.PROFILES`` dict
and the typed ``BedrockModelConfig`` default), the opinions live as named profiles:
built-in defaults ship in code and a project can override or extend them in
``warp/config/profiles.toml`` (user values win, deep-merged).

An agent then refers to a profile by name::

    model: economic        # → resolves to a model profile
    retry: low             # → resolves to a retry profile

or inlines its own config (passthrough for model, raw params for retry).

``profiles.toml`` shape::

    [model.fast]
    import_path = "strands.models.bedrock.BedrockModel"
    params = { model_id = "anthropic.claude-haiku-5-5" }

    [retry.aggressive]
    max_attempts = 6
    initial_delay = 2
    max_delay = 120

    [providers]
    my_provider = "my.pkg.CustomModel"
"""

from functools import lru_cache
from typing import Any

from omegaconf import OmegaConf
from pydantic import BaseModel, ConfigDict, Field

from loom.schemas.config.conversations import ConversationConfig
from loom.schemas.config.models import CustomModelConfig
from loom.schemas.config.retry import RetryConfig
from loom.utils.loaders import load_toml

# Built-in profiles. A project's warp/config/profiles.toml is deep-merged over these.
BUILTIN_PROFILES: dict[str, dict[str, dict[str, Any]]] = {
    "model": {
        "default": {
            "import_path": "strands.models.bedrock.BedrockModel",
            "params": {"model_id": "anthropic.claude-sonnet-5-5"},
        },
        "economic": {
            "import_path": "strands.models.bedrock.BedrockModel",
            "params": {"model_id": "anthropic.claude-haiku-5-5"},
        },
        "powerful": {
            "import_path": "strands.models.bedrock.BedrockModel",
            "params": {"model_id": "anthropic.claude-opus-5-5"},
        },
    },
    "retry": {
        "low": {"max_attempts": 3, "initial_delay": 1, "max_delay": 60},
        "medium": {"max_attempts": 4, "initial_delay": 2, "max_delay": 90},
        "high": {"max_attempts": 5, "initial_delay": 3, "max_delay": 120},
    },
    "conversation": {
        "none": {"strategy": "null"},
        "sliding": {
            "strategy": "sliding_window",
            "config": {"window_size": 20, "should_truncate_results": True},
        },
        "summarize": {
            "strategy": "summarizing",
            "config": {"summary_ratio": 0.3, "preserve_recent_messages": 10},
        },
    },
}

# Built-in provider aliases: short name → dotted path to a Strands Model class.
# An inline model config can name a class with ``provider:`` instead of the full
# ``import_path:``. A project's warp/config/profiles.toml [providers] table is
# deep-merged over these (user wins), so new providers need no library release.
BUILTIN_PROVIDERS: dict[str, str] = {
    "bedrock": "strands.models.bedrock.BedrockModel",
    "openai": "strands.models.openai.OpenAIModel",
    "openai_responses": "strands.models.openai_responses.OpenAIResponsesModel",
    "anthropic": "strands.models.anthropic.AnthropicModel",
    "gemini": "strands.models.gemini.GeminiModel",
    "litellm": "strands.models.litellm.LiteLLMModel",
    "ollama": "strands.models.ollama.OllamaModel",
    "mistral": "strands.models.mistral.MistralModel",
    "llamaapi": "strands.models.llamaapi.LlamaAPIModel",
    "llamacpp": "strands.models.llamacpp.LlamaCppModel",
    "sagemaker": "strands.models.sagemaker.SageMakerAIModel",
    "writer": "strands.models.writer.WriterModel",
}


class Profiles(BaseModel):
    """Resolved, validated set of named model, retry and conversation profiles."""

    model_config = ConfigDict(extra="forbid")

    model: dict[str, CustomModelConfig] = Field(default_factory=dict)
    retry: dict[str, RetryConfig] = Field(default_factory=dict)
    conversation: dict[str, ConversationConfig] = Field(default_factory=dict)
    providers: dict[str, str] = Field(default_factory=dict)


def _merge(builtin: dict, user: dict) -> dict:
    """Deep-merge user profiles over the built-ins (user wins)."""
    merged = OmegaConf.to_container(
        OmegaConf.merge(OmegaConf.create(builtin), OmegaConf.create(user)),
        resolve=True,
    )
    assert isinstance(merged, dict)
    return merged


@lru_cache(maxsize=1)
def get_profiles() -> Profiles:
    """Load and validate the merged profile set (built-ins + ``warp/config/profiles.toml``).

    Cached for the process; ``clear_config_caches`` resets it for the dev loop.
    """
    from loom.core.paths import build_workspace_paths

    ws = build_workspace_paths()
    user: dict[str, Any] = {}
    profiles_file = ws.profiles_file
    if profiles_file.is_file():
        user = load_toml(profiles_file) or {}

    builtin = {**BUILTIN_PROFILES, "providers": BUILTIN_PROVIDERS}
    merged = _merge(builtin, user)
    return Profiles(**merged)
