"""Map the agent YAML ``context`` field onto ``Agent(context_manager=...)``."""

from __future__ import annotations

from typing import Any

from loom.adapters.strands import capabilities
from loom.core.exceptions import AgentConfigError
from loom.utils.loaders import import_class_from_dotted_path


def get_context(value: str | dict[str, Any]) -> Any:
    """Return the value Strands accepts as ``context_manager``."""
    if not capabilities.agent_accepts("context_manager"):
        raise AgentConfigError(
            "The installed Strands version does not accept context_manager.",
            tip="Requiere strands-agents >= 1.43",
        )
    if value in ("auto", "agentic"):
        return value
    if value == "off":
        return False
    if isinstance(value, dict) and value.get("import_path"):
        cls = import_class_from_dotted_path(str(value["import_path"]))
        return cls(**dict(value.get("params") or {}))
    if isinstance(value, dict):
        return value
    raise AgentConfigError(
        f"Unknown context value: {value!r}.",
        tip="Use auto, agentic, off, a strategy dict, or import_path.",
    )


def conversation_is_none(conversation: Any) -> bool:
    """True when the resolved conversation would be a null manager."""
    if conversation is None or conversation == "none":
        return True
    from loom.core.loaders.conversation import resolve_conversation_config

    try:
        resolved = resolve_conversation_config(conversation)
    except AgentConfigError:
        return False
    return getattr(resolved, "strategy", None) == "null"
