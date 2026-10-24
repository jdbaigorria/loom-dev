"""Execution sandbox declared in ``app.yml``, with an optional per-agent override."""

from typing import Any

from pydantic import Field, model_validator

from ._validators import parse_single_key_dict
from .strict import StrictConfig


class SandboxConfig(StrictConfig):
    """``docker``, ``ssh``, or ``{import_path, params}``."""

    kind: str
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def parse(cls, data: Any) -> Any:
        if isinstance(data, dict) and "kind" in data:
            return data
        if isinstance(data, dict) and "import_path" in data:
            return {"kind": data["import_path"], "params": data.get("params") or {}}
        if isinstance(data, dict):
            name, params = parse_single_key_dict(data, "Sandbox")
            return {"kind": name, "params": params}
        raise ValueError("sandbox must be a docker, ssh, or import_path mapping.")
