"""Path resolution for Loom workspaces and bundled package assets.

Split by concern (the module was doing too much):

- ``assets``    — static locations of bundled scaffolding templates.
- ``naming``    — agent name normalization/validation rules.
- ``workspace`` — the ``WorkspacePaths`` map + factory + existence helpers.

Public names are re-exported here, so ``from loom.core.paths import X`` keeps
working::

    from loom.core.paths import build_workspace_paths, resolve_existing_agent_yaml
    from loom.core.paths import AGENT_TEMPLATES, normalize_agent_name
"""

from .assets import (
    AGENT_TEMPLATES,
    INIT_TEMPLATES,
    INTERNAL_PACKAGE_ROOT,
    TEMPLATES_DIR,
)
from .naming import normalize_agent_name, workspace_dir_name
from .workspace import (
    AgentPaths,
    MetadataPaths,
    WorkspacePaths,
    build_workspace_paths,
    resolve_existing_agent_yaml,
    resolve_existing_workflow_yaml,
)

__all__ = [
    "AGENT_TEMPLATES",
    "INIT_TEMPLATES",
    "INTERNAL_PACKAGE_ROOT",
    "TEMPLATES_DIR",
    "AgentPaths",
    "MetadataPaths",
    "WorkspacePaths",
    "build_workspace_paths",
    "normalize_agent_name",
    "workspace_dir_name",
    "resolve_existing_agent_yaml",
    "resolve_existing_workflow_yaml",
]
