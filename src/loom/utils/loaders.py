"""Configuration and file content loaders with caching and project root detection.

This module provides utilities for loading configuration files (YAML, TOML) and
text content with intelligent caching and project root detection.

Key Functions:

- **Project Root Detection** (get_project_root): Walks up the directory tree
  looking for loom.yml, .loom/, agents/ + config/, or pyproject.toml markers.

- **Configuration Loading**: load_yml() and load_toml() parse config files into
  Python dicts (with OmegaConf for YAML providing nested access).

- **File Content Loading**: load_file_content() reads text files with UTF-8 encoding.

Caching:

Functions are decorated with @cache to avoid re-parsing config files or re-reading
file content. The cache is memory-resident (persists for the process lifetime).

Usage:

    from loom.utils.loaders import load_config, load_file_content, get_project_root

    config = load_config("config/app.yml")  # Returns dict
    prompt = load_file_content("prompts/main.md")  # Returns str
    root = get_project_root()  # Returns Path
"""

import importlib
import importlib.util
import logging
import os
import sys
import warnings
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import cast

from omegaconf import DictConfig, OmegaConf

logger = logging.getLogger(__name__)


def get_project_root() -> Path:
    """Detect Loom project root by walking up directory tree.

    Detection order:

    1. **LOOM_ROOT environment variable** - If set, use this (allows override).
    2. **Loom marker files** - First ancestor with loom.yml, loom.toml, or .loom/
    3. **Workspace structure** - First ancestor with both agents/ and config/ dirs
    4. **Fallback** - First ancestor with pyproject.toml
    5. **Last resort** - Current working directory (with warning)

    Returns:
        Path: Detected project root directory.

    Warns:
        RuntimeWarning: If project root could not be reliably detected (returns cwd).
    """
    env_dir = os.environ.get("LOOM_ROOT")
    if env_dir:
        return Path(env_dir).resolve()

    current_dir = Path.cwd().resolve()

    for folder in [current_dir, *current_dir.parents]:
        if any(
            [
                (folder / "loom.yml").exists(),
                (folder / "loom.toml").exists(),
                (folder / ".loom").exists(),
            ]
        ):
            return folder

        if (folder / "agents").exists() and (folder / "config").exists():
            return folder

        if (folder / "pyproject.toml").exists():
            return folder

    warnings.warn(
        "Loom Warning: Project root could not be detected safely. "
        "Missing either the 'loom.yml' file or the 'agents/ + config/' structure. "
        "Using the current working directory, which may cause path errors.",
        RuntimeWarning,
    )
    return current_dir


def load_yml(path: Path) -> DictConfig:
    """Load YAML configuration file into OmegaConf DictConfig.

    Args:
        path: Path to YAML file.

    Returns:
        DictConfig: OmegaConf config object with nested dict-like access.
            Supports dot notation: config.database.host

    Raises:
        FileNotFoundError: If file does not exist.
        Exception: If YAML parsing fails.
    """
    if not path.exists():
        logger.error("YAML file not found: %s", path)
        raise FileNotFoundError(f"Yml not found: {path}")

    try:
        logger.debug("Loading YAML configuration from %s", path)
        config = OmegaConf.load(path)
        logger.debug("YAML loaded successfully: %s", path)
        if not isinstance(config, DictConfig):
            raise TypeError(f"Expected a mapping YAML file, got a list: {path}")
        return config
    except Exception as e:
        logger.error("Failed to load YAML file '%s': %s", path, str(e), exc_info=True)
        raise


def load_toml(path: Path) -> dict:
    """Load TOML configuration file into Python dict.

    Args:
        path: Path to TOML file.

    Returns:
        dict: Parsed TOML content as nested dictionary.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If TOML parsing fails.
    """
    import tomllib

    if not path.exists():
        logger.error("TOML file not found: %s", path)
        raise FileNotFoundError(f"TOML file not found: {path}")
    try:
        logger.debug("Loading TOML configuration from %s", path)
        with open(path, "rb") as f:
            data = tomllib.load(f)
        logger.debug("TOML loaded successfully: %s", path)
        return data
    except Exception as e:
        logger.error("Failed to load TOML file '%s': %s", path, str(e), exc_info=True)
        raise ValueError(f"Error loading toml config: {e}")


# Loaders for configs


@cache
def _load_absolute_config(abs_path: str) -> dict:
    """Load and resolve YAML config into plain Python dict (cached).

    Internal function wrapped by load_config(). Uses functools.cache for
    performance - all resolved configs are cached in memory.

    Args:
        abs_path: Absolute path to YAML file (as string for cache key).

    Returns:
        dict: Fully resolved configuration (OmegaConf references expanded).
    """
    path = Path(abs_path)
    config = load_yml(path)
    OmegaConf.resolve(config)
    result = OmegaConf.to_container(config, resolve=True)
    if not isinstance(result, dict):
        raise TypeError(f"Expected a dict after resolving config, got {type(result)}")
    return result


def load_config(config_path: str | Path) -> dict:
    """Load YAML configuration file into plain Python dict.

    Resolves the path to absolute form and delegates to cached _load_absolute_config().
    Resolves OmegaConf references and returns as standard Python dict.

    Args:
        config_path: Path to YAML file (absolute or relative to cwd).

    Returns:
        dict: Configuration as plain Python dictionary.

    Example:
        >>> config = load_config("config/app.yml")
        >>> print(config["database"]["host"])
    """
    return _load_absolute_config(str(Path(config_path).resolve()))


# Loaders for files (prompts)


@cache
def _load_file_content(abs_file_path: str) -> str:
    """Read file content as UTF-8 string (cached).

    Internal function wrapped by load_file_content(). Uses functools.cache for
    performance - file contents are cached in memory.

    Args:
        abs_file_path: Absolute path to file (as string for cache key).

    Returns:
        str: File content stripped of leading/trailing whitespace.

    Raises:
        FileNotFoundError: If file does not exist.
        IOError: If file reading fails.
    """
    path = Path(abs_file_path)

    if not path.is_file():
        logger.error("File not found: %s", path)
        raise FileNotFoundError(f"File not found: {path}")

    try:
        logger.debug("Reading file content from %s", path)
        with open(path, encoding="utf-8") as f:
            content = f.read().strip()
        logger.debug("File loaded successfully: %s (%d bytes)", path, len(content))
        return content
    except Exception as e:
        logger.error("Error reading file '%s': %s", path, str(e), exc_info=True)
        raise OSError(f"Error reading file '{path}': {e}")


_WORKSPACE_PATHS: list[Path] = []


def ensure_on_sys_path(path: Path) -> None:
    """Append ``path`` to ``sys.path`` once (compared by resolved path).

    Appended, never inserted first: a workspace file named like a stdlib module
    (``json.py``) must not shadow it for the whole process. The directory is also
    remembered so :func:`evict_workspace_modules` can drop what was imported from it.
    """
    resolved = path.resolve()
    if resolved not in _WORKSPACE_PATHS:
        _WORKSPACE_PATHS.append(resolved)
    entry = str(resolved)
    if not any(p and Path(p).resolve() == resolved for p in sys.path):
        sys.path.append(entry)


def evict_workspace_modules() -> None:
    """Drop from ``sys.modules`` every module loaded from a registered workspace dir.

    Used by the dev loop so an edited helper is re-imported on the next build.
    """
    for name, mod in list(sys.modules.items()):
        file = getattr(mod, "__file__", None)
        if file and any(Path(file).resolve().is_relative_to(d) for d in _WORKSPACE_PATHS):
            del sys.modules[name]
    importlib.invalidate_caches()


def import_module_from_file(file_path: Path, module_name: str) -> ModuleType:
    """Load a Python module from a file path.

    Args:
        file_path: Absolute path to the .py file.
        module_name: Logical name to assign to the module.

    Returns:
        The loaded module.

    Raises:
        ImportError: If the spec cannot be built or the loader is missing.
    """
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot build module spec from '{file_path}'")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def import_class_from_dotted_path(dotted_path: str) -> type:
    """Import a class using a fully-qualified dotted path (e.g. 'my.module.MyClass').

    Args:
        dotted_path: String in the form 'module.path.ClassName'.

    Returns:
        The class object.

    Raises:
        ImportError: If the module cannot be imported.
        AttributeError: If the class does not exist in the module.
        ValueError: If dotted_path has no dot separator.
    """
    if "." not in dotted_path:
        raise ValueError(f"Expected a dotted path like 'my.module.ClassName', got: '{dotted_path}'")
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return cast(type, getattr(module, class_name))


def import_attr(ref: str) -> object:
    """Import an attribute from an installed module by reference.

    Accepts two forms:

    - ``module.path:attr`` — the explicit, unambiguous form (matches the
      ``handler: module:fn`` convention); preferred for plugin code.
    - ``module.path.attr`` — back-compat dotted form (last segment is the attr).

    This is how config references *code* without a local file — the only way a
    non-filesystem ConfigSource (e.g. a document DB) can point at tools/hooks/
    output classes shipped as an installed package.

    Raises:
        ValueError: If ``ref`` has neither a ``:`` nor a ``.`` separator.
        ImportError: If the module cannot be imported.
        AttributeError: If the attribute does not exist in the module.
    """
    if ":" in ref:
        module_path, attr = ref.split(":", 1)
    elif "." in ref:
        module_path, attr = ref.rsplit(".", 1)
    else:
        raise ValueError(f"Expected 'module:attr' or 'module.attr', got: '{ref}'")
    module = importlib.import_module(module_path)
    return getattr(module, attr)


def load_file_content(file_path: str | Path) -> str:
    """Load text file content as UTF-8 string.

    Resolves path to absolute form and delegates to cached _load_file_content().
    Content is automatically stripped of leading/trailing whitespace.

    Args:
        file_path: Path to text file (absolute or relative to cwd).

    Returns:
        str: File content stripped of whitespace.

    Raises:
        FileNotFoundError: If file does not exist.
        IOError: If file reading fails.

    Example:
        >>> prompt = load_file_content("prompts/system.md")
        >>> print(prompt)
    """
    return _load_file_content(str(Path(file_path).resolve()))
