"""
loom.core.loaders.output — Load the Pydantic class for structured output.

Resolves the structured output class in two ways:

- **Dotted module path** (``my.module.MyClass``): standard import with
  ``importlib.import_module``.
- **Simple name** (``MyClass``): searches for the class in ``{agent_dir}/output.py``.
"""

import logging
from pathlib import Path
from typing import cast

from pydantic import BaseModel

from loom.core.exceptions import OutputLoadError
from loom.utils.loaders import import_attr, import_module_from_file

logger = logging.getLogger(__name__)


def get_output_class(output_config: str, agent_dir: Path | None) -> type[BaseModel]:
    """Load and return the Pydantic class for the agent's structured output.

    Args:
        output_config: Pydantic class name. Can be a dotted import
            (``my.pkg:MyModel`` / ``my.pkg.MyModel``) or just the class name
            (``MyModel``, searched in ``{agent_dir}/output.py``).
        agent_dir: Agent directory where ``output.py`` is searched for a bare
            class name. ``None`` when there is no local filesystem — only the
            dotted-import form is resolvable then.

    Returns:
        The class (not an instance) that inherits from ``pydantic.BaseModel``.

    Raises:
        OutputLoadError: If a local class is referenced without a filesystem
            locator, or the module/class cannot be imported.
    """
    if ":" in output_config or "." in output_config:
        logger.debug("Loading output class via import path: '%s'", output_config)
        try:
            return cast(type[BaseModel], import_attr(output_config))
        except (ImportError, AttributeError, ValueError) as e:
            raise OutputLoadError(
                message=f"Failed to import output class: {str(e)}",
                tip=f"Verify '{output_config}' points at an installed Pydantic class (module:Class).",
            ) from e

    if agent_dir is None:
        raise OutputLoadError(
            message=f"Output class '{output_config}' is local but no filesystem locator is available.",
            tip="Reference it as 'module:Class' (installed code), or build from a filesystem-backed source.",
        )

    output_file = agent_dir / "output.py"
    if not output_file.is_file():
        raise OutputLoadError(
            message=f"Output file not found: {output_file}",
            tip=f"Create '{output_file}' with a Pydantic class named '{output_config}'.",
        )

    logger.debug("Loading output class '%s' from '%s'", output_config, output_file)
    try:
        module = import_module_from_file(output_file, f"{agent_dir.name}.output")
    except ImportError as e:
        raise OutputLoadError(
            message=f"Failed to load output module: {str(e)}",
            tip=f"Check that '{output_file}' is valid Python.",
        ) from e

    if not hasattr(module, output_config):
        raise OutputLoadError(
            message=f"Class '{output_config}' not found in '{output_file}'.",
            tip=f"Define a Pydantic class named '{output_config}' in that file.",
        )

    return cast(type[BaseModel], getattr(module, output_config))
