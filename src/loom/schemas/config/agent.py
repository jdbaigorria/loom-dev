"""Schema for a single agent's YAML configuration."""

from typing import Literal

from pydantic import model_validator

from .conversations import ConversationConfig
from .hook import HookConfig
from .mcp import MCPServerConfig
from .models import ModelConfig
from .plugin import PluginConfig
from .prompt import PromptConfig
from .retry import RetryStrategyConfig
from .strict import StrictConfig
from .tool import ToolConfig


class AgentConfig(StrictConfig):
    """Complete configuration for a Loom agent as defined in its YAML file."""

    name: str
    # "agent" → strands.Agent; "bidi" → experimental full-duplex BidiAgent
    # (voice/streaming). Bidi reuses every loader except the model (a BidiModel)
    # and omits conversation/structured-output/retry. Gated by capability + extra.
    kind: Literal["agent", "bidi"] = "agent"
    description: str = "Agent created by Loom"
    system_prompt: PromptConfig = PromptConfig(prompt="prompt.md")
    # Profile name (resolved from loom.config.profiles) or an inline config.
    model: ModelConfig = "default"
    # Profile name or inline model for SDK side calls (summary, memory, classifiers).
    aux_model: ModelConfig | None = None
    retry: RetryStrategyConfig = "low"
    output: str | None = None
    tools: list[ToolConfig] | None = None
    mcp_servers: list[MCPServerConfig] | None = None
    hooks: list[HookConfig] | None = None
    plugins: list[PluginConfig] | None = None
    # auto | agentic | off, a strategy dict, or {import_path, params}.
    context: str | dict | None = None
    # How tools are executed within a single turn. None → Strands default
    # (concurrent). Requires a Strands build with pluggable tool executors.
    tool_executor: Literal["concurrent", "sequential"] | None = None
    # Profile name or an inline conversation config. None → the app.yml conversation.
    conversation: str | ConversationConfig | None = None
    # Written by `loom agent new`. Kept so extra="forbid" does not reject existing agents.
    version: str | None = None

    @model_validator(mode="after")
    def _bidi_rejects_unsupported(self):
        if self.kind != "bidi":
            return self
        if self.conversation is not None:
            raise ValueError("'conversation' is not supported when kind is 'bidi'.")
        if self.plugins is not None:
            raise ValueError("'plugins' is not supported when kind is 'bidi'.")
        if self.context is not None:
            raise ValueError("'context' is not supported when kind is 'bidi'.")
        if self.aux_model is not None:
            raise ValueError("'aux_model' is not supported when kind is 'bidi'.")
        if not isinstance(self.model, str):
            from loom.schemas.config.models import CustomModelConfig

            if not isinstance(self.model, CustomModelConfig):
                raise ValueError("model fallback is not supported when kind is 'bidi'.")
        return self

    @model_validator(mode="after")
    def _aux_model_is_a_single_model(self):
        if self.aux_model is None:
            return self
        from loom.schemas.config.models import CustomModelConfig

        if not isinstance(self.aux_model, (str, CustomModelConfig)):
            raise ValueError("aux_model cannot be a fallback or a list.")
        return self
