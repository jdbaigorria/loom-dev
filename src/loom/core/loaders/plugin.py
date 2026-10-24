"""Build Strands plugins from an agent YAML list."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

from loom.adapters import strands as sx
from loom.adapters.strands import capabilities
from loom.core.exceptions import AgentConfigError
from loom.core.loaders.model import get_model
from loom.schemas.config.plugin import PluginConfig
from loom.utils.loaders import import_class_from_dotted_path, import_module_from_file

logger = logging.getLogger(__name__)

_BUILTIN = {
    "skills": "strands.vended_plugins.skills.AgentSkills",
    "context_offloader": "strands.vended_plugins.context_offloader.ContextOffloader",
    "goal": "strands.vended_plugins.goal.GoalLoop",
}


def get_plugins(
    plugins: list[PluginConfig],
    plugins_dir: Path | None,
    config_dir: Path | None = None,
) -> list[Any]:
    """Instantiate each declared plugin. A new instance is built on every call."""
    if not capabilities.agent_accepts("plugins"):
        raise AgentConfigError(
            "The installed Strands version does not accept plugins.",
            tip="Requiere strands-agents >= 1.34",
        )
    return [_one(item, plugins_dir, config_dir) for item in plugins]


def _one(item: PluginConfig, plugins_dir: Path | None, config_dir: Path | None) -> Any:
    params = dict(item.params or {})
    if "." in item.name:
        cls = import_class_from_dotted_path(item.name)
    elif item.name in _BUILTIN:
        cls = sx.resolve(_BUILTIN[item.name], optional=True)
        if cls is None:
            raise AgentConfigError(
                f"Built-in plugin '{item.name}' is not available in this Strands build."
            )
    else:
        cls = _local_class(item.name, plugins_dir)
    params = _prepare(item.name, params, config_dir, cls)
    try:
        instance = cls(**params) if params else cls()
    except TypeError as exc:
        raise AgentConfigError(f"Plugin '{item.name}' rejected its parameters: {exc}") from exc
    if sx.Plugin is not None and not isinstance(instance, sx.Plugin):
        raise AgentConfigError(f"Plugin '{item.name}' did not return a Strands Plugin.")
    return instance


def _local_class(name: str, plugins_dir: Path | None) -> type:
    if plugins_dir is None:
        raise AgentConfigError(
            f"Plugin '{name}' is local but no workspace is available.",
            tip="Use a built-in plugin or a dotted import path.",
        )
    path = plugins_dir / f"{name}.py"
    if not path.is_file():
        raise AgentConfigError(
            f"Plugin '{name}' was not found.",
            tip=f"Create {path} or use one of {sorted(_BUILTIN)}.",
        )
    module = import_module_from_file(path, f"plugins.{name}")
    class_name = name.title().replace("_", "")
    cls = getattr(module, class_name, None)
    if cls is None:
        raise AgentConfigError(
            f"Plugin file {path.name} has no class {class_name}.",
        )
    return cast(type, cls)


def _prepare(
    name: str, params: dict[str, Any], config_dir: Path | None, cls: type
) -> dict[str, Any]:
    if name == "skills" and config_dir is not None and "skills" in params:
        params["skills"] = _resolve_skill_paths(params["skills"], config_dir)
    if name == "goal" and isinstance(params.get("judge"), dict):
        params["judge"] = _judge(params["judge"])
    return params


def _resolve_skill_paths(skills: Any, config_dir: Path) -> Any:
    if isinstance(skills, str):
        path = Path(skills)
        return str(path if path.is_absolute() else config_dir / path)
    if isinstance(skills, list):
        return [_resolve_skill_paths(item, config_dir) for item in skills]
    return skills


def _judge(raw: dict[str, Any]) -> Any:
    judge_cls = sx.resolve("strands.vended_plugins.goal.plugin.JudgeConfig", optional=True)
    data = dict(raw)
    if "model" in data and data["model"] is not None:
        data["model"] = get_model(data["model"])
    if judge_cls is None:
        return data
    return judge_cls(**data)
