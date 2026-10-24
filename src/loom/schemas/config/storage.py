"""Shared storage backend declared in ``app.yml``."""

from typing import Any, Literal

from pydantic import model_validator

from ._validators import parse_single_key_dict
from .strict import StrictConfig


class StorageConfig(StrictConfig):
    """``local``, ``s3`` or ``memory`` storage for subsystems that do not set their own."""

    kind: Literal["local", "s3", "memory"]
    base_dir: str | None = None
    bucket: str | None = None
    prefix: str = ""
    region_name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def parse(cls, data: Any) -> Any:
        if data == "memory":
            return {"kind": "memory"}
        if isinstance(data, str):
            raise ValueError("storage must be 'memory' or a single-key mapping (local or s3).")
        if isinstance(data, dict) and "kind" not in data:
            name, params = parse_single_key_dict(data, "Storage")
            if name not in ("local", "s3", "memory"):
                raise ValueError(f"Unknown storage '{name}'. Use local, s3 or memory.")
            return {"kind": name, **params}
        return data

    @model_validator(mode="after")
    def _s3_needs_a_bucket(self) -> "StorageConfig":
        if self.kind == "s3" and not self.bucket:
            raise ValueError("s3 storage requires a bucket.")
        return self
