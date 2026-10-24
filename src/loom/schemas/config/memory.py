"""Agent memory stores and the manager that injects them."""

from typing import Any

from pydantic import Field, model_validator

from ._validators import parse_single_key_dict
from .strict import StrictConfig


class MemoryStoreConfig(StrictConfig):
    """One store: ``file``, ``bedrock_kb``, or a dotted import path."""

    kind: str
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def parse(cls, data: Any) -> Any:
        if isinstance(data, dict) and "kind" in data:
            return data
        if isinstance(data, dict):
            name, params = parse_single_key_dict(data, "Memory store")
            return {"kind": name, "params": params}
        raise ValueError("A memory store must be a single-key mapping.")


class MemoryConfig(StrictConfig):
    """``memory:`` on an agent. Nothing is attached when the field is omitted."""

    stores: list[MemoryStoreConfig] = Field(min_length=1)
    search_tool: bool | dict[str, Any] = True
    add_tool: bool | dict[str, Any] = False
    injection: bool | dict[str, Any] = True
