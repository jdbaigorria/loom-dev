"""Schema for a tool entry in an agent's YAML configuration."""

from typing import Any, Literal

from pydantic import model_validator

from ._validators import parse_single_key_dict
from .strict import StrictConfig

ToolSource = Literal["file", "shared", "builtin", "import"]

# Prefix in the YAML tool name → resolution source. Bare names default to "file".
_SOURCE_PREFIXES: dict[str, ToolSource] = {
    "shared.": "shared",
    "builtin.": "builtin",
}


def _split_source(raw_name: str) -> tuple[str, ToolSource]:
    """Map a YAML tool reference to ``(name, source)``.

    A ``:`` marks a dotted import (``module:fn`` — installed plugin code); the full
    reference is kept as the name. Otherwise a ``shared.``/``builtin.`` prefix
    selects the source; a bare name defaults to ``file``.
    """
    if ":" in raw_name:
        return raw_name, "import"
    for prefix, source in _SOURCE_PREFIXES.items():
        if raw_name.startswith(prefix):
            return raw_name.split(".", 1)[1], source
    return raw_name, "file"


class ToolConfig(StrictConfig):
    """Configuration for a single tool attached to an agent.

    ``source`` records where the tool is resolved from:

    - ``file`` (default): a ``{name}.py`` in the agent's ``tools/`` directory.
    - ``shared``: a ``{name}.py`` in the workspace shared ``tools/`` directory.
    - ``builtin``: a factory shipped with Loom (e.g. ``builtin.kb``,
      ``builtin.apicall``), looked up in ``loom.builtins.BUILTIN_TOOLS``.
    """

    name: str
    params: dict[str, Any] | None = None
    source: ToolSource = "file"
    # Registry key of the builtin this tool specialises, when ``name`` is a
    # *logical* tool name distinct from the builtin (e.g. a ``{name}.yaml`` that
    # the ConfigSource resolved to ``builtin: apicall``). When ``None`` and
    # ``source == "builtin"``, ``name`` itself is the registry key.
    builtin: str | None = None

    @property
    def is_shared(self) -> bool:
        """Back-compat accessor: ``True`` when the tool lives in the shared dir."""
        return self.source == "shared"

    @property
    def is_builtin(self) -> bool:
        """``True`` when the tool is a Loom-packaged builtin factory."""
        return self.source == "builtin"

    @property
    def registry_key(self) -> str:
        """The ``BUILTIN_TOOLS`` key to resolve: the explicit ``builtin`` target
        if set (a named specialisation), otherwise ``name``."""
        return self.builtin or self.name

    @model_validator(mode="before")
    @classmethod
    def parse_mixed_list(cls, data: Any) -> Any:
        """Normalise bare strings and single-key dicts into a ToolConfig dict.

        An already-structured mapping (one carrying an explicit ``name`` key, e.g.
        produced by ConfigSource hydration) passes through untouched.
        """
        if isinstance(data, str):
            name, source = _split_source(data)
            return {"name": name, "params": {}, "source": source}

        if isinstance(data, dict):
            if "name" in data:  # already structured (hydrated/explicit) — leave as-is
                return data
            raw_name, params = parse_single_key_dict(data, "Tool")
            name, source = _split_source(raw_name)
            return {"name": name, "params": params, "source": source}

        return data
