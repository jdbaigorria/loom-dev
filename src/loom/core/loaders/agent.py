"""
loom.core.loaders.agent — Load and validate an agent's YAML configuration.

Entry point for obtaining a Pydantic-validated ``AgentConfig`` from the path
to the YAML file. Uses ``@cache`` to avoid re-reading from disk on repeated
calls within the same process.
"""

import logging
from functools import cache
from pathlib import Path

from loom.schemas.config.agent import AgentConfig
from loom.utils.loaders import load_config

logger = logging.getLogger(__name__)


@cache
def get_agent_config(config_file_path: str | Path) -> AgentConfig:
    """Load and validate an agent's configuration from a YAML file.

    The result is cached by ``config_file_path`` to avoid repeated disk reads
    within the same process.

    Args:
        config_file_path: Absolute path to the agent's YAML file.

    Returns:
        Validated ``AgentConfig`` with all fields from the YAML.

    Raises:
        AgentNotFoundError: If the file does not exist.
        AgentConfigError: If the YAML does not match the ``AgentConfig`` schema.
    """
    logger.debug("Loading agent config from '%s'", config_file_path)
    config = load_config(config_file_path)
    return AgentConfig(**config)
