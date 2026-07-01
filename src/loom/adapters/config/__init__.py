"""loom.adapters.config — Adapters for the :class:`~loom.ports.ConfigSource` port.

Default adapter: :class:`FileConfigSource`, which reads declarative config from
the workspace folder (the historical behaviour). Future adapters (e.g. a
document-DB source) live here too and produce the *same* validated objects.
"""

from loom.adapters.config.file_source import FileConfigSource

__all__ = ["FileConfigSource"]
