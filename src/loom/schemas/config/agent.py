"""Schema for a single agent's YAML configuration."""

from typing import Literal

from pydantic import BaseModel

from .hook import HookConfig
from .mcp import MCPServerConfig
from .models import ModelConfig
from .prompt import PromptConfig
from .retry import RetryStrategyConfig
from .tool import ToolConfig


class AgentConfig(BaseModel):
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
    retry: RetryStrategyConfig = "low"
    output: str | None = None
    tools: list[ToolConfig] | None = None
    mcp_servers: list[MCPServerConfig] | None = None
    hooks: list[HookConfig] | None = None
    # How tools are executed within a single turn. None → Strands default
    # (concurrent). Requires a Strands build with pluggable tool executors.
    tool_executor: Literal["concurrent", "sequential"] | None = None
