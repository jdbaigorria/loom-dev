"""Map ``background_tasks`` onto the dict or ``True`` that Strands accepts."""

from __future__ import annotations

from loom.adapters.strands import capabilities
from loom.core.exceptions import AgentConfigError
from loom.schemas.config.background import BackgroundTasksConfig


def get_background_tasks(
    value: bool | BackgroundTasksConfig, tool_names: set[str]
) -> bool | dict:
    """Return ``True`` or a ``BackgroundTasksConfig`` dict."""
    if not capabilities.agent_accepts("background_tasks"):
        raise AgentConfigError(
            "The installed Strands version does not accept background_tasks.",
            tip="Requiere strands-agents >= 1.55.1",
        )
    if isinstance(value, bool):
        return value
    missing = [
        name
        for name in [*(value.always or []), *(value.never or []), *(value.agentic or [])]
        if name not in tool_names
    ]
    if missing:
        raise AgentConfigError(
            f"background_tasks names are not tools of this agent: {missing}",
            tip=f"Declare them under tools. Known tools: {sorted(tool_names) or '(none)'}.",
        )
    return {key: item for key, item in value.model_dump().items() if item is not None}
