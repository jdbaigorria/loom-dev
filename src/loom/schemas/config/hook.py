"""Schema for a hook entry in an agent's YAML configuration."""

from typing import Any

from pydantic import BaseModel, model_validator

from ._validators import parse_single_key_dict


class HookConfig(BaseModel):
    """Configuration for a single lifecycle hook attached to an agent."""

    name: str
    params: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def parse_mixed_list(cls, data: Any) -> Any:
        """Normalise bare strings and single-key dicts into a HookConfig dict."""
        if isinstance(data, str):
            return {"name": data, "params": {}}

        if isinstance(data, dict):
            name, params = parse_single_key_dict(data, "Hook")
            return {"name": name, "params": params}

        return data
