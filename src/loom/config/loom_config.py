"""Loom project configuration loading and management.

Loads workspace-level configuration from loom.toml, with fallback to
loom.yml if TOML file is not found. Supports:

- Workspace name configuration
- Tool and hook directories
- Custom paths for agents, templates, etc.

Configuration Loading:

The loader searches for configuration in this order:
1. `loom.toml` in project root
2. `loom.yml` in project root (fallback if TOML not found)
3. Returns default LoomConfig if neither file exists

Configuration Format:

TOML format with optional [workspace] section::

    [workspace]
    workspace_name = "warp"          # Custom workspace dir name
    # ... other settings

Usage:

    from loom.config.loom_config import get_loom_config

    config = get_loom_config()
    print(config.workspace_name)       # "warp" (default)
"""

import warnings

from loom.schemas.config.loom import LoomConfig
from loom.utils.loaders import get_project_root, load_toml


def get_loom_config() -> LoomConfig:
    """Load Loom project configuration from loom.toml or loom.yml.

    Detects project root and attempts to load configuration from:
    1. `loom.toml` (preferred)
    2. `loom.yml` (fallback)
    3. Returns default LoomConfig if neither file exists

    Configuration file may contain a [workspace] section with custom settings,
    or settings at root level (both formats supported).

    Returns:
        LoomConfig: Validated configuration object with workspace settings
            (workspace_name, etc.). Returns defaults if no config file found.

    Example:
        >>> config = get_loom_config()
        >>> print(config.workspace_name)
        warp

        >>> # Custom config in loom.toml
        >>> # [workspace]
        >>> # workspace_name = "my_workspace"
        >>> config = get_loom_config()
        >>> print(config.workspace_name)
        my_workspace
    """
    root_dir = get_project_root()
    toml_path = root_dir / "loom.toml"

    if not toml_path.is_file():
        toml_path = root_dir / ".loom"

    if not toml_path.is_file():
        return LoomConfig()

    data = load_toml(toml_path)
    # loom.toml uses [workspace] section; if not present, assumes root-level config
    config_data = dict(data.get("workspace", data)) if data else {}

    # Legacy: `region` used to live in loom.toml. It now belongs in app.yml
    # (AppConfig). Drop it here (instead of failing on extra="forbid") so existing
    # projects keep loading; warn so the author moves it.
    if "region" in config_data:
        config_data.pop("region")
        warnings.warn(
            "'region' in loom.toml is deprecated and ignored — set it in app.yml "
            "instead. Remove it from loom.toml to silence this warning.",
            DeprecationWarning,
            stacklevel=2,
        )

    return LoomConfig.model_validate(config_data) if config_data else LoomConfig()
