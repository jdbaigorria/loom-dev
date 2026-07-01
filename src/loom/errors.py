"""loom.errors — Loom's **public** exception surface.

The errors that Loom's public API raises and that external code is expected to
catch (or, for a custom :class:`~loom.ports.ConfigSource` adapter, to *raise* to
honour the port contract). They live in ``loom.core.exceptions`` as
implementation; this module is the stability boundary — import them from here, not
from ``loom.core``.

``LoomError`` is the catch-all base. The rest mirror the families documented on
:func:`loom.build_agent` / :func:`loom.build_workflow` and the ``ConfigSource``
port: agent/workflow not-found and config errors, target resolution, and the
tool/output/hook/model load errors raised while assembling an agent.
"""

from __future__ import annotations

from loom.core.exceptions import (
    AgentConfigError,
    AgentError,
    AgentNotFoundError,
    HookLoadError,
    LoomError,
    ModelLoadError,
    OutputLoadError,
    TargetResolutionError,
    ToolLoadError,
    ToolSelectionError,
    WorkflowConfigError,
    WorkflowError,
    WorkflowNotFoundError,
)

__all__ = [
    "AgentConfigError",
    "AgentError",
    "AgentNotFoundError",
    "HookLoadError",
    "LoomError",
    "ModelLoadError",
    "OutputLoadError",
    "TargetResolutionError",
    "ToolLoadError",
    "ToolSelectionError",
    "WorkflowConfigError",
    "WorkflowError",
    "WorkflowNotFoundError",
]
