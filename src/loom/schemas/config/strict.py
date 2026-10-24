"""Shared strict-config behavior: unknown keys fail and name a close match."""

import difflib
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator


class StrictConfig(BaseModel):
    """Reject keys that are not fields, and suggest a close match."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="wrap")
    @classmethod
    def _reject_unknown_keys(cls, data: Any, handler):
        try:
            return handler(data)
        except ValidationError as exc:
            extras = [
                err
                for err in exc.errors()
                if err["type"] == "extra_forbidden" and len(err["loc"]) == 1
            ]
            if not extras:
                raise
            known = set(cls.model_fields)
            for info in cls.model_fields.values():
                if info.alias:
                    known.add(info.alias)
            parts: list[str] = []
            for err in extras:
                key = str(err["loc"][-1])
                match = difflib.get_close_matches(key, sorted(known), n=1, cutoff=0.6)
                if match:
                    parts.append(f"{key!r} (did you mean {match[0]!r}?)")
                else:
                    parts.append(repr(key))
            raise ValueError("Unknown config key(s): " + ", ".join(parts)) from exc
