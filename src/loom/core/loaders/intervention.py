"""Build Strands intervention handlers from the agent YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.adapters import strands as sx
from loom.adapters.strands import capabilities
from loom.core.exceptions import AgentConfigError
from loom.schemas.config.intervention import InterventionConfig
from loom.utils.loaders import import_attr, import_class_from_dotted_path

_CALLBACKS = ("ask", "evaluate", "evaluate_trust")


def get_interventions(
    configs: list[InterventionConfig],
    tool_names: set[str],
    config_dir: Path | None,
) -> list[Any]:
    """Return handler instances. Order is the YAML order."""
    if not capabilities.agent_accepts("interventions"):
        raise AgentConfigError(
            "The installed Strands version does not accept interventions.",
            tip="Requiere strands-agents >= 1.43",
        )
    return [_build(config, tool_names, config_dir) for config in configs]


def _build(config: InterventionConfig, tool_names: set[str], config_dir: Path | None) -> Any:
    params = dict(config.params)
    if config.name == "hitl":
        _check_tools(params.get("allowed_tools") or [], tool_names)
        for key in _CALLBACKS:
            if isinstance(params.get(key), str) and params[key] != "stdio":
                params[key] = import_attr(params[key])
        # ask omitted → Confirm interrupts. `loom agent run` resumes those
        # through AgentResponse.interrupts. ask: stdio blocks on stdin inside
        # the turn. A dotted ask callback runs inline.
        handler = sx.HumanInTheLoop(**params)
    elif config.name == "cedar":
        if sx.CedarAuthorization is None:
            raise AgentConfigError(
                "Cedar interventions need the optional cedar extra.",
                tip="pip install 'loom-declarative[cedar]'",
            )
        handler = sx.CedarAuthorization(**_read_cedar_files(params, config_dir))
    elif "." in config.name or ":" in config.name:
        cls = import_class_from_dotted_path(config.name)
        handler = cls(**params)
    else:
        raise AgentConfigError(
            f"Unknown intervention '{config.name}'.",
            tip="Use hitl, cedar, or a dotted import path.",
        )
    if sx.InterventionHandler is not None and not isinstance(handler, sx.InterventionHandler):
        raise AgentConfigError(f"Intervention '{config.name}' is not an InterventionHandler.")
    return handler


def _check_tools(allowed: list[str], tool_names: set[str]) -> None:
    missing = []
    for name in allowed:
        bare = name[1:] if name.startswith("!") else name
        if bare == "*":
            continue
        if bare not in tool_names:
            missing.append(name)
    if missing:
        raise AgentConfigError(
            f"allowed_tools names are not tools of this agent: {missing}",
            tip=f"Declare them under tools. Known tools: {sorted(tool_names) or '(none)'}.",
        )


def _read_cedar_files(params: dict[str, Any], config_dir: Path | None) -> dict[str, Any]:
    resolved = dict(params)
    for key in ("policies", "entities", "schema"):
        value = resolved.get(key)
        if not isinstance(value, str) or config_dir is None:
            continue
        path = Path(value)
        if not path.is_absolute():
            path = config_dir / value
        if path.is_file():
            resolved[key] = path.read_text(encoding="utf-8")
    return resolved
