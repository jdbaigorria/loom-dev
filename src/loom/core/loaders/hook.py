"""
loom.core.loaders.hook — Dynamic hook loading from the agent YAML.

Resolves hooks in three steps (same pattern as the tool loader):

1. **Built-in LOOM** (simple name in ``REGISTRY``): imports the registered class.
2. **Fully qualified** (dotted name): imports the module and extracts the class.
3. **Local** (simple name without dots and not in REGISTRY): looks for
   ``{hooks_dir}/{name}.py`` and instantiates the class named as the PascalCase
   of the filename.

Each instantiated hook implements ``strands.hooks.HookProvider`` and is passed
directly to the ``hooks=`` parameter of ``strands.Agent``.
"""

import inspect
import logging
from pathlib import Path
from typing import cast

from loom.adapters.strands import HookProvider
from loom.core.exceptions import HookLoadError
from loom.schemas.config.hook import HookConfig
from loom.utils.loaders import import_attr, import_class_from_dotted_path, import_module_from_file

logger = logging.getLogger(__name__)

# Registry of built-in LOOM hooks
REGISTRY: dict[str, str] = {
    "logging": "loom.hooks.logging_hook.LoggingHook",
    "tool_tracker": "loom.hooks.tool_tracker.ToolTrackerHook",
    "rate_limit": "loom.hooks.rate_limit.RateLimitHook",
}


def _require_provider_class(obj: object, name: str) -> type:
    """Return ``obj`` if it is a class with ``register_hooks``, else raise.

    Hooks are Strands ``HookProvider`` classes. Without this check a function
    reference would be *called* with no arguments and fail with an unrelated error.
    """
    if isinstance(obj, type) and hasattr(obj, "register_hooks"):
        return obj
    got = "a function" if callable(obj) else type(obj).__name__
    raise HookLoadError(
        f"Hook '{name}' is not a HookProvider class.",
        tip=f"Hooks must be HookProvider classes with 'register_hooks'; got {got}. "
        "See docs/guides/hooks.md.",
    )


def _load_hook(hook_def: HookConfig, hooks_dir: Path | None) -> HookProvider:
    """Load and instantiate a single hook.

    Args:
        hook_def: Hook configuration with ``name`` and optional ``params``.
        hooks_dir: Directory where local workspace hooks are searched, or ``None``
            when there is no local filesystem (only registry/dotted hooks then).

    Returns:
        ``HookProvider`` instance ready to pass to ``strands.Agent``.

    Raises:
        HookLoadError: If a local hook is referenced without a filesystem locator,
            or the hook does not exist, cannot be imported, or has no valid class.
    """
    name = hook_def.name
    params = hook_def.params or {}

    # 1. Built-in LOOM
    if name in REGISTRY:
        logger.debug("Loading built-in hook '%s' from '%s'", name, REGISTRY[name])
        try:
            hook_class = _require_provider_class(
                import_class_from_dotted_path(REGISTRY[name]), name
            )
            hook_instance = hook_class(**params) if params else hook_class()
            logger.debug(
                "Hook '%s' instantiated with params=%s", name, list(params.keys()) if params else []
            )
            return cast(HookProvider, hook_instance)
        except (ImportError, AttributeError, TypeError) as e:
            raise HookLoadError(
                f"Built-in hook '{name}' failed to load.",
                tip=f"Error: {str(e)}",
            ) from e

    # 2. Fully qualified import (e.g. my.pkg.MyHook or my.pkg:MyHook)
    if ":" in name or "." in name:
        logger.debug("Loading hook via qualified import: '%s'", name)
        try:
            hook_class = _require_provider_class(import_attr(name), name)
            hook_instance = hook_class(**params) if params else hook_class()
            logger.debug(
                "Hook '%s' instantiated with params=%s", name, list(params.keys()) if params else []
            )
            return cast(HookProvider, hook_instance)
        except (ImportError, AttributeError, TypeError) as e:
            module_path = name.rsplit(".", 1)[0]
            raise HookLoadError(
                f"Hook '{name}' could not be imported.",
                tip=f"Verify that '{module_path}' is installed and the class exists.",
            ) from e

    # 3. Local: warp/hooks/{name}.py
    if hooks_dir is None:
        raise HookLoadError(
            f"Hook '{name}' is local but no filesystem locator is available.",
            tip="Use a built-in hook, reference installed code as 'module:Class', "
            "or build from a filesystem-backed source.",
        )
    hook_file = hooks_dir / f"{name}.py"
    if not hook_file.is_file():
        raise HookLoadError(
            f"Hook '{name}' not found.",
            tip=f"Create the file at {hook_file} or use a built-in hook: {list(REGISTRY.keys())}.",
        )

    logger.debug("Loading local hook '%s' from '%s'", name, hook_file)
    try:
        module = import_module_from_file(hook_file, f"hooks.{name}")
        logger.debug("Local hook module loaded: hooks.%s", name)

        # Convention: PascalCase class derived from the filename
        class_name = name.title().replace("_", "")
        if hasattr(module, class_name):
            hook_class = _require_provider_class(getattr(module, class_name), name)
            try:
                hook_instance = hook_class(**params) if params else hook_class()
                logger.debug(
                    "Hook '%s' instantiated with class '%s' (params=%s)",
                    name,
                    class_name,
                    list(params.keys()) if params else [],
                )
                return cast(HookProvider, hook_instance)
            except TypeError as te:
                logger.error(
                    "Failed to instantiate hook '%s' with params %s: %s",
                    name,
                    params,
                    str(te),
                    exc_info=True,
                )
                raise HookLoadError(
                    f"Could not instantiate hook '{class_name}' with provided params.",
                    tip=f"Params: {params}. Error: {str(te)}",
                ) from te

        # Fallback: first class in the module that implements HookProvider
        logger.debug("Falling back to first HookProvider class in module %s", module)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is not HookProvider and isinstance(obj, type) and hasattr(obj, "register_hooks"):
                try:
                    hook_instance = obj(**params) if params else obj()
                    logger.debug(
                        "Hook '%s' instantiated with fallback class '%s'", name, obj.__name__
                    )
                    return cast(HookProvider, hook_instance)
                except TypeError as te:
                    logger.error(
                        "Failed to instantiate fallback hook '%s': %s",
                        obj.__name__,
                        str(te),
                        exc_info=True,
                    )
                    raise

        raise HookLoadError(
            f"No HookProvider class found in '{hook_file}'.",
            tip=f"Define a class '{class_name}' that inherits from HookProvider and implements 'register_hooks'.",
        )
    except HookLoadError:
        raise
    except Exception as e:
        logger.error(
            "Failed to load local hook '%s' from %s: %s", name, hook_file, str(e), exc_info=True
        )
        raise HookLoadError(
            f"Failed to load local hook '{name}'.",
            tip=f"Error: {str(e)}",
        ) from e


def get_hooks(hook_defs: list[HookConfig], hooks_dir: Path | None) -> list[HookProvider]:
    """Load all hooks declared in the agent configuration.

    Args:
        hook_defs: List of ``HookConfig`` from the agent YAML.
        hooks_dir: Local workspace hooks directory (``warp/hooks/``), or ``None``
            when there is no local filesystem (only registry/dotted hooks then).

    Returns:
        List of ``HookProvider`` instances ready to pass to ``strands.Agent``.

    Raises:
        HookLoadError: If any hook does not exist, cannot be imported, or has no valid class.
    """
    hooks = []
    for hook_def in hook_defs:
        hook = _load_hook(hook_def, hooks_dir)
        hooks.append(hook)
        logger.debug("Hook '%s' loaded: %s", hook_def.name, type(hook).__name__)

    logger.info("Loaded %d hook(s)", len(hooks))
    return hooks
