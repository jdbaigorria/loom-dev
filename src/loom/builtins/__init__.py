"""Built-in tools shipped with Loom.

A *builtin* is a factory ``make_*(**params) -> DecoratedFunctionTool`` that an
agent references in YAML via the ``builtin.<name>`` prefix::

    tools:
      - builtin.kb:
          kb_ids: [docs, tickets]
      - builtin.apicall:
          name: weather_api
          base_url: https://api.weather.com
          allowed_paths: ["/v1/*"]

The factory pattern (rather than a pre-decorated class method) is required so
each instance can set its Strands tool name at ``@tool(name=...)`` decoration
time — the only way to mount several instances of the same builtin without a
tool-name collision (Strands forbids both renaming after construction and
duplicate names).

Resolution happens in :mod:`loom.core.loaders.tool`, which looks the name up in
:data:`BUILTIN_TOOLS` before falling back to the filesystem.
"""

from collections.abc import Callable

from loom.adapters.strands import DecoratedFunctionTool

from .apicall import make_apicall
from .kb import make_kb

BuiltinFactory = Callable[..., "DecoratedFunctionTool | list[DecoratedFunctionTool]"]

#: Registry of builtin name → factory. Extend here to add a new builtin.
BUILTIN_TOOLS: dict[str, BuiltinFactory] = {
    "kb": make_kb,
    "apicall": make_apicall,
}

__all__ = ["BUILTIN_TOOLS", "BuiltinFactory", "make_apicall", "make_kb"]
