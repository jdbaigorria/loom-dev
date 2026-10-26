"""
loom.core.loaders.tool — Dynamic tool loading from Python files.

Imports Python modules at runtime and extracts callables decorated with
``@tool`` (Strands). Supports two patterns:

- **Class-based**: the file defines a ``MyTool`` class with ``@tool`` methods.
  If the YAML declares ``params``, the class is instantiated with them.
- **Module-level**: the file defines ``@tool`` functions directly, without
  a containing class.

Tools can be located in the agent's local directory (``agent_dir/tools/``)
or in the workspace shared directory (``shared_dir/tools/``).
"""

import inspect
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from loom.core.exceptions import ToolLoadError
from loom.schemas.config.tool import ToolConfig
from loom.utils.loaders import import_attr, import_module_from_file, load_config

logger = logging.getLogger(__name__)

#: Extensions recognised as a declarative (YAML) tool definition.
_TOOL_YAML_EXTS = ("yaml", "yml")


def _find_tool_class(module) -> type | None:
    """Find the first class in the module that has methods decorated with @tool.

    Args:
        module: Imported Python module to inspect.

    Returns:
        The found class, or ``None`` if the module has none.
    """
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ != module.__name__:
            continue
        if any(hasattr(m, "tool_spec") for _, m in inspect.getmembers(obj)):
            return obj
    return None


def _load_builtin(
    tool_def: ToolConfig, overlay: dict[str, Any] | None = None
) -> list[Callable[[Any], Any]]:
    """Resolve a builtin tool from the Loom-packaged registry.

    Handles both shapes:

    - **Plain builtin** (``builtin.kb``): ``tool_def.name`` is the registry key;
      the factory is called with ``params`` (which may carry its own ``name``).
    - **Named specialisation** (a resolved ``{name}.yaml``): ``tool_def.builtin``
      is the registry key and ``tool_def.name`` is the logical tool name, passed
      as ``name=`` to the factory.

    ``overlay`` is the same per-run overlay dict passed to :func:`get_tools` —
    typically credentials such as a Bedrock ``boto_session``. It is filtered down
    to the keys the resolved factory's signature actually declares before being
    merged into ``params``, so passing it is a no-op for builtins (like
    ``apicall``) that don't opt in via a matching parameter name.

    Raises:
        ToolLoadError: If the builtin is unknown or its params are invalid.
    """
    # Imported lazily: the builtins pull in heavy optional deps (boto3, requests)
    # only when one is actually configured, keeping the loader import-light.
    from loom.builtins import BUILTIN_TOOLS

    key = tool_def.registry_key
    factory = BUILTIN_TOOLS.get(key)
    if factory is None:
        raise ToolLoadError(
            f"Builtin tool '{key}' not found.",
            tip=f"Available builtins: {sorted(BUILTIN_TOOLS)}",
        )
    params = tool_def.params or {}
    if overlay:
        accepted = inspect.signature(factory).parameters
        params = {**params, **{k: v for k, v in overlay.items() if k in accepted}}
    try:
        # A named specialisation forces the logical name; a plain builtin lets its
        # params decide (preserving the existing generic/domain apicall contract).
        result = factory(name=tool_def.name, **params) if tool_def.builtin else factory(**params)
    except (TypeError, ValueError) as exc:
        raise ToolLoadError(
            f"Failed to build builtin '{key}' (tool '{tool_def.name}'): {exc}",
            tip="Check this tool's params/spec.",
        ) from exc

    tools = result if isinstance(result, list) else [result]
    logger.debug("Builtin '%s' loaded as '%s': %d callable(s)", key, tool_def.name, len(tools))
    return tools


def yaml_tool_to_config(name: str, spec: dict[str, Any]) -> ToolConfig:
    """Turn a declarative ``{name}.yaml`` spec into a builtin ``ToolConfig``.

    A YAML tool specialises a packaged builtin: it must declare ``builtin: <key>``
    plus that builtin's params (e.g. ``bind``/``expose`` for ``apicall``), and must
    not set ``name`` (the file stem is the tool name). The result is a builtin
    ``ToolConfig`` whose ``name`` is the logical tool name and whose ``builtin``
    is the registry key — so a declarative tool is indistinguishable from a builtin
    once resolved. Pure (no I/O): shared by the loader and ConfigSource hydration.

    Raises:
        ToolLoadError: If the spec lacks ``builtin`` or sets ``name``.
    """
    spec = dict(spec)  # don't mutate the caller's dict
    if "builtin" not in spec:
        raise ToolLoadError(
            f"Tool '{name}' must declare 'builtin: <name>'.",
            tip="A YAML tool specialises a packaged builtin, e.g. 'builtin: apicall'.",
        )
    if "name" in spec:
        raise ToolLoadError(
            f"Tool '{name}' must not set 'name'.",
            tip=f"The file name is the tool name ('{name}'); remove the 'name' key.",
        )
    builtin_target = spec.pop("builtin")
    return ToolConfig(name=name, source="builtin", builtin=builtin_target, params=spec)


def _load_yaml_tool(
    name: str, path: Path, overlay: dict[str, Any] | None = None
) -> list[Callable[[Any], Any]]:
    """Compile a declarative tool defined in a ``{name}.yaml`` file (unhydrated path).

    Reads the file and routes it through :func:`yaml_tool_to_config` +
    :func:`_load_builtin` — the same path a ConfigSource-hydrated tool takes.
    """
    # load_config resolves OmegaConf refs (incl. ${oc.env:...}) into a plain dict,
    # so a YAML tool gets the same env resolution as the agent YAML.
    return _load_builtin(yaml_tool_to_config(name, load_config(path)), overlay)


def _load_import_tool(tool_def: ToolConfig) -> list[Callable[[Any], Any]]:
    """Load a tool referenced by dotted import (``module:fn`` — installed code).

    Resolves the reference to a ``@tool`` function or a class with ``@tool``
    methods (instantiated with ``params``). No filesystem: this is the path a
    non-filesystem ConfigSource uses for code.

    Raises:
        ToolLoadError: If the reference can't be imported or isn't a valid tool.
    """
    ref = tool_def.name
    try:
        obj = import_attr(ref)
    except (ImportError, AttributeError, ValueError) as exc:
        raise ToolLoadError(
            f"Tool '{ref}' could not be imported.",
            tip="Use 'module.path:attr' pointing at an installed @tool function or class.",
        ) from exc

    if inspect.isclass(obj):
        instance = obj(**tool_def.params) if tool_def.params else obj()
        tools = [m for _, m in inspect.getmembers(instance) if hasattr(m, "tool_spec")]
        if not tools:
            raise ToolLoadError(
                f"Imported tool class '{ref}' has no @tool methods.",
                tip="Decorate at least one method with @tool.",
            )
        logger.debug("Import tool '%s' loaded: %d callable(s)", ref, len(tools))
        return tools

    if hasattr(obj, "tool_spec"):
        if tool_def.params:
            raise ToolLoadError(
                f"Imported tool '{ref}' is a function and cannot take params.",
                tip="Point at a class with @tool methods to receive params.",
            )
        return [cast(Callable[[Any], Any], obj)]

    raise ToolLoadError(
        f"'{ref}' is not a @tool function or a class with @tool methods.",
        tip="Decorate it with @tool, or point at a class that has @tool methods.",
    )


def _load_tool(
    tool_def: ToolConfig,
    agent_dir: Path | None,
    shared_dir: Path | None,
    overlay: dict[str, Any] | None = None,
) -> list[Callable[[Any], Any]]:
    """Load a single tool and return its Strands callables.

    Args:
        tool_def: Tool configuration with ``name``, ``source``, and
            optional ``params``.
        agent_dir: Agent root directory (for local tools), or ``None`` when there
            is no local filesystem (builtin/import tools don't need it).
        shared_dir: Workspace shared tools directory, or ``None``.
        overlay: Optional per-run overlay (e.g. a Bedrock ``boto_session``)
            offered to builtin tools — see :func:`_load_builtin`. Ignored by
            local/import tools.

    Returns:
        List of ``@tool``-decorated callables found in the module (or builtin).

    Raises:
        ToolLoadError: If a local tool is referenced without a filesystem locator,
            the file/builtin does not exist, the module has no class to receive
            ``params``, or contains no valid tools.
    """
    if tool_def.is_builtin:
        return _load_builtin(tool_def, overlay)

    if tool_def.source == "import":
        return _load_import_tool(tool_def)

    base_dir = shared_dir if tool_def.is_shared else (agent_dir / "tools" if agent_dir else None)
    if base_dir is None:
        raise ToolLoadError(
            f"Tool '{tool_def.name}' is a local file but no filesystem locator is available.",
            tip="Reference installed code as 'module:fn', or build from a filesystem-backed source.",
        )
    tool_file = base_dir / f"{tool_def.name}.py"
    yaml_files = [
        p for ext in _TOOL_YAML_EXTS if (p := base_dir / f"{tool_def.name}.{ext}").is_file()
    ]

    # A name must resolve to exactly one definition; .py and .yaml together is ambiguous.
    if tool_file.is_file() and yaml_files:
        raise ToolLoadError(
            f"Tool '{tool_def.name}' is defined as both .py and {yaml_files[0].suffix}.",
            tip=f"Keep one definition in {base_dir}.",
        )
    if yaml_files:
        if tool_def.params:
            raise ToolLoadError(
                f"Tool '{tool_def.name}' is a YAML definition and cannot take inline params.",
                tip=f"Put its config in {yaml_files[0].name}, reference it as '- {tool_def.name}'.",
            )
        return _load_yaml_tool(tool_def.name, yaml_files[0], overlay)

    if not tool_file.is_file():
        raise ToolLoadError(
            f"Tool '{tool_def.name}' not found.",
            tip=f"Expected a {tool_def.name}.py or {tool_def.name}.yaml in: {base_dir}",
        )

    logger.debug(
        "Loading tool '%s' from '%s' (shared=%s)",
        tool_def.name,
        tool_file,
        tool_def.is_shared,
    )

    owner = "shared" if tool_def.is_shared else f"agents.{agent_dir.name}" if agent_dir else "local"
    module_name = f"loom_workspace.{owner}.{tool_def.name}"
    module = import_module_from_file(tool_file, module_name)

    loaded_tools = []
    tool_class = _find_tool_class(module)

    if tool_class is not None:
        instance = tool_class(**tool_def.params) if tool_def.params else tool_class()
        for name, method in inspect.getmembers(instance):
            if hasattr(method, "tool_spec"):
                loaded_tools.append(method)
    else:
        if tool_def.params:
            raise ToolLoadError(
                f"Tool '{tool_def.name}' declares params but no tool class was found in the module.",
                tip=f"Define a class with @tool methods in {tool_file} to receive the params.",
            )
        for name, obj in inspect.getmembers(module):
            if hasattr(obj, "tool_spec") and name != "tool":
                loaded_tools.append(obj)

    if not loaded_tools:
        raise ToolLoadError(
            f"No valid tools found in '{tool_def.name}'.",
            tip=f"Decorate at least one function or method with @tool in {tool_file}.",
        )

    logger.debug("Tool '%s' loaded: %d callable(s)", tool_def.name, len(loaded_tools))
    return loaded_tools


def get_tools(
    tool_defs: list[ToolConfig],
    agent_dir: Path | None,
    shared_dir: Path | None,
    overlay: dict[str, Any] | None = None,
) -> list[Callable[[Any], Any]]:
    """Load all tools declared in the agent configuration.

    Args:
        tool_defs: List of ``ToolConfig`` from the agent YAML.
        agent_dir: Agent root directory, or ``None`` when there is no local
            filesystem (only builtin/import tools are resolvable then).
        shared_dir: Workspace shared tools directory, or ``None``.
        overlay: Optional per-run overlay dict (e.g. a Bedrock ``boto_session``)
            offered to every builtin tool's factory, filtered to the parameter
            names it actually declares (see :func:`_load_builtin`) — the same
            per-run channel :func:`loom.core.loaders.model.get_model` uses for
            the model, so a builtin that needs the caller's real credentials
            (like ``builtin.kb``) opts in just by declaring that parameter.

    Returns:
        Flat list of Strands callables from all loaded tools.

    Raises:
        ToolLoadError: If any tool does not exist, is missing a class for params, or has no tool_spec.
    """
    tools = []
    for tool_def in tool_defs:
        tools.extend(_load_tool(tool_def, agent_dir, shared_dir, overlay))

    logger.info("Loaded %d tool(s)", len(tools))
    return tools
