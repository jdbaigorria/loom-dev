"""Build the shared Strands storage backend from ``app.yml``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.adapters import strands as sx
from loom.adapters.strands import capabilities
from loom.core.exceptions import AgentConfigError
from loom.schemas.config.storage import StorageConfig


def get_storage(
    config: StorageConfig,
    *,
    metadata_dir: Path | None,
    sandbox: Any = None,
    overlay: dict[str, Any] | None = None,
) -> Any:
    """Return a ``LocalFileStorage``, ``S3Storage`` or ``InMemoryStorage``."""
    if not capabilities.agent_accepts("storage"):
        raise AgentConfigError(
            "The installed Strands version does not accept storage.",
            tip="Requiere strands-agents >= 1.52",
        )
    if sx.LocalFileStorage is None or sx.S3Storage is None or sx.InMemoryStorage is None:
        raise AgentConfigError(
            "The installed Strands version does not provide a storage backend.",
            tip="Requiere strands-agents >= 1.52",
        )
    if config.kind == "memory":
        return sx.InMemoryStorage()
    if config.kind == "local":
        base = (
            Path(config.base_dir)
            if config.base_dir
            else (metadata_dir or Path(".loom")) / "storage"
        )
        return sx.LocalFileStorage(str(base), sandbox=sandbox)
    session = (overlay or {}).get("boto_session")
    return sx.S3Storage(
        bucket=config.bucket or "",
        prefix=config.prefix,
        region_name=config.region_name,
        boto_session=session,
    )
