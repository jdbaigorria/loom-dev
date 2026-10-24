from typing import Annotated, Any, Literal, Self

from pydantic import Field, model_validator

from .strict import StrictConfig

# Conversation strategies


class SummarizationAgentConfig(StrictConfig):
    # None → the loader uses the 'economic' model profile (no hardcoded model id).
    model_id: str | None = None
    temperature: float = 0.1
    max_tokens: int = 1024


class SlidingWindowConfig(StrictConfig):
    window_size: int = 10
    should_truncate_results: bool = True
    per_turn: bool | int = False


class SummarizingConfig(StrictConfig):
    summary_ratio: float = 0.3
    preserve_recent_messages: int = 10
    summarization_agent: SummarizationAgentConfig | None = None
    summarization_system_prompt: str | None = None

    @model_validator(mode="after")
    def resolve_exclusive_fields(self) -> Self:
        if self.summarization_agent is not None and self.summarization_system_prompt is not None:
            raise ValueError(
                "'summarization_agent' and 'summarization_system_prompt' are mutually exclusive. "
                "Use 'summarization_agent' to provide a full agent config, "
                "or 'summarization_system_prompt' for a simple prompt string — not both."
            )
        return self


class NullStrategy(StrictConfig):
    strategy: Literal["null"]
    config: None = None


class SlidingWindowsStrategy(StrictConfig):
    strategy: Literal["sliding_window"]
    config: SlidingWindowConfig


class SummarizingStrategy(StrictConfig):
    strategy: Literal["summarizing"]
    config: SummarizingConfig


class CustomStrategy(StrictConfig):
    """Conversation manager backed by a user-provided ``ConversationManager`` subclass.

    Loom ships ``null``/``sliding_window``/``summarizing``; any other strategy
    plugs in here by dotted ``import_path``, mirroring the model ``custom``
    passthrough. The resolved class is built with the ``config`` params as keyword
    arguments — Loom validates nothing inside ``config``.
    """

    strategy: Literal["custom"]
    import_path: str = Field(
        description="Dotted path to a strands ConversationManager subclass, e.g. 'my.pkg:MyCM'.",
    )
    config: dict[str, Any] = Field(default_factory=dict)


ConversationConfig = Annotated[
    NullStrategy | SlidingWindowsStrategy | SummarizingStrategy | CustomStrategy,
    Field(discriminator="strategy"),
]
