"""
loom.core.loaders.workflow — Load and validate a workflow's YAML configuration.

Returns a Pydantic-validated ``WorkflowConfig`` (a ``graph`` or ``swarm`` variant
resolved by the ``type`` discriminator) from the path to the YAML file.
"""

import logging
from functools import cache
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from loom.core.exceptions import WorkflowConfigError
from loom.schemas.config.workflow import (
    GraphWorkflowConfig,
    SwarmWorkflowConfig,
    WorkflowConfig,
)
from loom.utils.loaders import load_config

logger = logging.getLogger(__name__)

_ADAPTER: TypeAdapter[GraphWorkflowConfig | SwarmWorkflowConfig] = TypeAdapter(WorkflowConfig)


@cache
def get_workflow_config(config_file_path: str | Path) -> GraphWorkflowConfig | SwarmWorkflowConfig:
    """Load and validate a workflow configuration from a YAML file.

    Cached by ``config_file_path`` to avoid repeated disk reads in one process.

    Args:
        config_file_path: Absolute path to the workflow YAML file.

    Returns:
        Validated ``GraphWorkflowConfig`` or ``SwarmWorkflowConfig``.

    Raises:
        WorkflowConfigError: If the YAML does not match the workflow schema.
    """
    logger.debug("Loading workflow config from '%s'", config_file_path)
    config = load_config(config_file_path)
    try:
        return _ADAPTER.validate_python(config)
    except ValidationError as e:
        raise WorkflowConfigError(
            f"Invalid workflow configuration in '{config_file_path}'.",
            tip=str(e),
        ) from e
