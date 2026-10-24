"""Intervention handlers declared on an agent."""

from typing import Any

from pydantic import Field, model_validator

from ._validators import parse_single_key_dict
from .strict import StrictConfig


class InterventionConfig(StrictConfig):
    """One handler: ``hitl``, ``cedar``, or a dotted import path."""

    name: str
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def parse(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"name": data, "params": {}}
        if isinstance(data, dict) and "name" in data:
            return data
        if isinstance(data, dict):
            name, params = parse_single_key_dict(data, "Intervention")
            return {"name": name, "params": params}
        return data
