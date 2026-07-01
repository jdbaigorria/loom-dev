"""loom.ports — Abstract interfaces (ports) that decouple the engine from I/O.

A *port* is a ``typing.Protocol`` describing a capability Loom needs without
binding to a concrete implementation. Adapters in :mod:`loom.adapters` implement
them. This is the seam that lets ``build()`` receive validated config objects
instead of reading the filesystem itself (dependency inversion).

Current ports:

- :class:`~loom.ports.config_source.ConfigSource` — where declarative config
  (``AgentConfig`` / ``AppConfig``) comes from. Default adapter:
  :class:`loom.adapters.config.FileConfigSource` (the workspace folder).
"""

from loom.ports.config_source import ConfigSource

__all__ = ["ConfigSource"]
