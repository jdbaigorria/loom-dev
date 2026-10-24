"""Structured output declaration: a class path, optionally with a prompt."""

from pydantic import ConfigDict, Field

from .strict import StrictConfig


class StructuredOutputConfig(StrictConfig):
    """``output: {class, prompt}`` on an agent."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    output_class: str = Field(alias="class")
    prompt: str | None = None
