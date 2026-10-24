"""Schema for a plugin entry in an agent's YAML."""

from typing import Any

from pydantic import model_validator

from ._validators import parse_single_key_dict
from .strict import StrictConfig


class PluginConfig(StrictConfig):
    """One Strands plugin: a built-in name, a dotted path, or a local file."""

    name: str
    params: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def parse_mixed_list(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"name": data, "params": {}}
        if isinstance(data, dict):
            if "name" in data:
                return data
            name, params = parse_single_key_dict(data, "Plugin")
            return {"name": name, "params": params}
        return data
