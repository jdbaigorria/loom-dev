"""Load and merge application YAML configuration (app.yml and per-environment overlays)."""

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from omegaconf import OmegaConf

from loom.schemas.config.app import AppConfig
from loom.utils.loaders import load_config, load_yml

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_app_config(config_file_path: str | Path) -> AppConfig:
    """Load application configuration from file (cached).

    Loads and validates a single app.yml file without environment-specific
    overrides. For environment-aware loading with override support, use
    load_app_config_with_env() instead.

    Uses functools.lru_cache to avoid re-parsing the same file.

    Args:
        config_file_path: Path to app.yml configuration file.

    Returns:
        AppConfig: Validated application configuration object.

    Raises:
        ValueError: If configuration validation fails.
    """
    config = load_config(config_file_path)
    return AppConfig(**config)


def resolve_env() -> str:
    """Return the active environment: LOOM_ENV variable or 'dev' by default."""
    return os.environ.get("LOOM_ENV", "dev")


def load_app_config_with_env(env: str, config_dir: Path) -> AppConfig:
    """Load ``app.yml`` and apply overrides from ``app.{env}.yml`` if it exists.

    Args:
        env: Environment name (e.g. ``"dev"``, ``"prod"``).
        config_dir: Directory containing the ``app.yml`` files and their overrides.

    Returns:
        ``AppConfig`` with base values merged with the environment override.
    """
    logger.debug("Loading app configuration for environment '%s' from %s", env, config_dir)
    try:
        base_path = config_dir / "app.yml"
        base = load_yml(base_path)
        logger.debug("Base app configuration loaded from %s", base_path)

        override_path = config_dir / f"app.{env}.yml"
        if override_path.exists():
            override = load_yml(override_path)
            merged = OmegaConf.merge(base, override)
            logger.info(
                "App configuration overrides from '%s' applied for environment '%s'",
                override_path,
                env,
            )
        else:
            merged = base
            logger.debug("No environment-specific overrides found at %s", override_path)

        raw = OmegaConf.to_container(merged, resolve=True)
        if not isinstance(raw, dict):
            raise TypeError(f"Expected app config to be a dict, got {type(raw)}")
        app_config = AppConfig(**cast(dict[str, Any], raw))
        logger.debug("App configuration loaded successfully for environment '%s'", env)
        return app_config
    except Exception as e:
        logger.error(
            "Failed to load app configuration for environment '%s': %s", env, str(e), exc_info=True
        )
        raise
