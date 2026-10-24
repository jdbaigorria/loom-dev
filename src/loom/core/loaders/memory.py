"""Build a ``MemoryManager`` from the agent ``memory`` block."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.adapters import strands as sx
from loom.adapters.strands import capabilities
from loom.core.exceptions import AgentConfigError
from loom.schemas.config.memory import MemoryConfig
from loom.schemas.context import LoomSession
from loom.utils.loaders import import_class_from_dotted_path


def get_memory(
    config: MemoryConfig,
    session: LoomSession,
    *,
    metadata_dir: Path | None,
    storage: Any = None,
    overlay: dict[str, Any] | None = None,
) -> Any:
    """Return a ``MemoryManager``. Placeholders ``{user_id}`` and ``{session_id}`` are resolved."""
    if not capabilities.agent_accepts("memory_manager"):
        raise AgentConfigError(
            "The installed Strands version does not accept memory_manager.",
            tip="Requiere strands-agents >= 1.44",
        )
    if (
        sx.MemoryManager is None
        or sx.FileMemoryStore is None
        or sx.BedrockKnowledgeBaseStore is None
    ):
        raise AgentConfigError(
            "The installed Strands version does not provide memory stores.",
            tip="Requiere strands-agents >= 1.44",
        )
    stores = [
        _build_store(
            store.kind, _placeholders(store.params, session), metadata_dir, storage, overlay
        )
        for store in config.stores
    ]
    return sx.MemoryManager(
        stores,
        search_tool_config=config.search_tool,
        add_tool_config=config.add_tool,
        injection=config.injection,
    )


def _placeholders(value: Any, session: LoomSession) -> Any:
    if isinstance(value, str):
        return value.replace("{user_id}", session.user_id).replace(
            "{session_id}", session.session_id
        )
    if isinstance(value, dict):
        return {key: _placeholders(item, session) for key, item in value.items()}
    if isinstance(value, list):
        return [_placeholders(item, session) for item in value]
    return value


def _build_store(kind: str, params: dict[str, Any], metadata_dir, storage, overlay) -> Any:
    if kind == "file":
        if "storage" not in params:
            params = {
                **params,
                "storage": storage
                if storage is not None
                else sx.LocalFileStorage(str((metadata_dir or Path(".loom")) / "memory")),
            }
        return sx.FileMemoryStore(**params)
    if kind == "bedrock_kb":
        return sx.BedrockKnowledgeBaseStore(**_with_boto_session(params, overlay))
    if "." in kind or ":" in kind:
        cls = import_class_from_dotted_path(kind)
        return cls(**params)
    raise AgentConfigError(
        f"Unknown memory store '{kind}'.",
        tip="Use file, bedrock_kb, or a dotted import path.",
    )


def _with_boto_session(params: dict[str, Any], overlay: dict[str, Any] | None) -> dict[str, Any]:
    session = (overlay or {}).get("boto_session")
    if session is None:
        return params
    config = dict(params.get("config") or {})
    if "runtime_client" not in config:
        region = config.get("region_name")
        config["runtime_client"] = session.client("bedrock-agent-runtime", region_name=region)
    if "agent_client" not in config:
        config["agent_client"] = session.client(
            "bedrock-agent", region_name=config.get("region_name")
        )
    return {**params, "config": config}
