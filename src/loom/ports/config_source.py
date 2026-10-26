"""loom.ports.config_source — The ``ConfigSource`` port.

Abstracts *where declarative config comes from*. The engine (``build()``) asks a
``ConfigSource`` for a validated ``AgentConfig`` / ``AppConfig`` by name instead
of reading YAML off disk itself. The default adapter
(:class:`loom.adapters.config.FileConfigSource`) reads the workspace folder; a
future adapter can read a document DB and return the *same* validated objects,
leaving the engine untouched.

Scope — **declarative only.** A ``ConfigSource`` never serves *code* (tool
``.py`` modules, ``output.py``, hooks): code is resolved by import (and, in a
non-filesystem source, only by dotted path — a packaged plugin). See
``.docs/design-config-source.md``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig
from loom.schemas.config.workflow import GraphWorkflowConfig, SwarmWorkflowConfig
from loom.schemas.target import TargetInfo, TargetKind


@runtime_checkable
class ConfigSource(Protocol):
    """Source of validated, declarative Loom configuration.

    Implementations return fully validated Pydantic objects, not raw dicts — the
    engine assumes its input is already well-formed (validation is the source's
    responsibility, at whatever boundary it loads from).
    """

    def get_agent_config(self, name: str) -> AgentConfig:
        """Return the validated ``AgentConfig`` for ``name``.

        Raises:
            AgentNotFoundError: If no config exists for ``name``.
            AgentConfigError: If the config fails validation.
        """
        ...

    def get_app_config(self, env: str | None = None) -> AppConfig:
        """Return the validated ``AppConfig``, optionally for environment ``env``.

        ``env`` selects an environment overlay when the source supports one
        (the file adapter merges ``app.{env}.yml``); sources without the notion
        may ignore it.
        """
        ...

    def get_workflow_config(self, name: str) -> GraphWorkflowConfig | SwarmWorkflowConfig:
        """Return the validated workflow config (``Graph``/``Swarm`` variant) for ``name``.

        Workflows compose agents by name (the engine builds each node via this
        same source), so a workflow document carries only orchestration — nodes,
        edges/agents, entry point — never the agent definitions themselves.

        Raises:
            WorkflowNotFoundError: If no workflow exists for ``name``.
            WorkflowConfigError: If the config fails validation.
        """
        ...

    def list_targets(self) -> list[TargetInfo]:
        """Return every buildable target (name + kind + description + labels).

        The discovery contract: the caller (backend/harness) learns *what exists*
        and *of which kind* without importing or hard-coding anything. ``kind`` is
        the source's own property, not inferred at the call site. Each
        ``TargetInfo.labels`` must be the labels of the target's *effective* config,
        i.e. what the source's ``get_agent_config`` returns for it.
        """
        ...

    def get_target_kind(self, name: str, kind: TargetKind | None = None) -> TargetKind:
        """Resolve a single ``name`` to its kind.

        Args:
            name: Target name.
            kind: Optional explicit kind to disambiguate a name that exists as
                more than one (still validated against the source).

        Raises:
            TargetResolutionError: If ``name`` exists as no target, or as several
                with no ``kind`` to disambiguate.
        """
        ...
