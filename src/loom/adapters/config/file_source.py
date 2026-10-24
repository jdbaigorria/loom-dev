"""loom.adapters.config.file_source — Workspace-folder ``ConfigSource``.

Default adapter for the :class:`~loom.ports.ConfigSource` port: resolves an agent
name to its YAML in the workspace (``warp/agents/{name}/config/{name}.yml``) and
the app config to ``warp/config/app.yml`` (with an optional ``app.{env}.yml``
overlay). This is the historical behaviour, now behind the port so the engine no
longer reaches into the filesystem itself.

It also owns the ``app.yml`` ``defaults`` → agent merge (formerly inline in
``core.builder``, the GAP-03 path), so there is a *single* place that produces an
``AgentConfig`` instead of two divergent branches.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from omegaconf import OmegaConf

from loom.core.exceptions import TargetResolutionError, ToolLoadError
from loom.core.loaders.agent import get_agent_config
from loom.core.loaders.app import load_app_config_with_env, resolve_env
from loom.core.loaders.prompt import hydrate_prompt
from loom.core.loaders.tool import yaml_tool_to_config
from loom.core.loaders.workflow import get_workflow_config
from loom.core.paths import (
    build_workspace_paths,
    resolve_existing_agent_yaml,
    resolve_existing_workflow_yaml,
)
from loom.core.paths.workspace import WorkspacePaths
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig
from loom.schemas.config.tool import ToolConfig
from loom.schemas.config.workflow import GraphWorkflowConfig, SwarmWorkflowConfig
from loom.schemas.target import TargetInfo, TargetKind
from loom.utils.loaders import load_config

_TOOL_YAML_EXTS = ("yaml", "yml")

logger = logging.getLogger(__name__)


class FileConfigSource:
    """Read declarative config from the project's workspace folder.

    Args:
        workspace: Resolved workspace paths. Defaults to
            :func:`build_workspace_paths` (detects the project root on disk).
        env: Active environment for the ``app.{env}.yml`` overlay. Defaults to
            :func:`resolve_env` (``LOOM_ENV`` or ``"dev"``) at call time.
    """

    def __init__(self, workspace: WorkspacePaths | None = None, env: str | None = None) -> None:
        self._ws = workspace or build_workspace_paths()
        self._env = env

    @property
    def workspace(self) -> WorkspacePaths:
        """The resolved workspace paths backing this source."""
        return self._ws

    def get_app_config(self, env: str | None = None) -> AppConfig:
        active_env = env or self._env or resolve_env()
        return load_app_config_with_env(active_env, self._ws.app_dir)

    def get_agent_config(self, name: str, *, env: str | None = None) -> AgentConfig:
        """Return the agent's ``AgentConfig``, merged with ``app.yml`` defaults and
        with its prompt hydrated to literal text.

        When ``app.yml`` declares ``defaults``, they are deep-merged under the
        agent YAML (agent wins). Otherwise the agent YAML is loaded directly via
        the cached :func:`get_agent_config` loader. The system prompt's file/dir
        sources are then resolved to text (so ``build()`` never reads them off
        disk).
        """
        agent_yaml = resolve_existing_agent_yaml(self._ws, name)
        app_config = self.get_app_config(env)

        if not app_config.defaults:
            agent_config = get_agent_config(agent_yaml)
        else:
            agent_raw = load_config(agent_yaml)
            merged_raw = OmegaConf.to_container(
                OmegaConf.merge(
                    OmegaConf.create(app_config.defaults),
                    OmegaConf.create(agent_raw),
                ),
                resolve=True,
            )
            if not isinstance(merged_raw, dict):
                raise TypeError(f"Expected merged config to be a dict, got {type(merged_raw)}")
            agent_config = AgentConfig(**cast(dict[str, Any], merged_raw))

        return self._hydrate(agent_config, name)

    def get_workflow_config(self, name: str) -> GraphWorkflowConfig | SwarmWorkflowConfig:
        """Return the workflow's config from ``warp/workflows/{name}.yml``.

        Raises:
            WorkflowNotFoundError: If the YAML does not exist.
            WorkflowConfigError: If it fails validation.
        """
        return get_workflow_config(resolve_existing_workflow_yaml(self._ws, name))

    # ------------------------------------------------------------------
    # Discovery (catalog)
    # ------------------------------------------------------------------

    def list_targets(self) -> list[TargetInfo]:
        """Enumerate agents (``warp/agents/{name}/``) and workflows (``warp/workflows/*.yml``).

        Kind is inferred from *where* the definition lives — the one place that
        inference is allowed to live (this adapter), not the call site. Descriptions
        are read best-effort: a malformed definition yields an empty string rather
        than breaking discovery. ``bidi`` agents are not yet distinguished here.
        """
        targets: list[TargetInfo] = []

        agents_dir = self._ws.agents_dir
        if agents_dir.is_dir():
            for entry in sorted(p for p in agents_dir.iterdir() if p.is_dir()):
                if self._ws.agent(entry.name).yaml_file.exists():
                    kind = self._agent_kind(entry.name)
                    targets.append(
                        TargetInfo(entry.name, kind, self._safe_description("agent", entry.name))
                    )

        workflows_dir = self._ws.workflows_dir
        if workflows_dir.is_dir():
            for wf in sorted(workflows_dir.glob("*.yml")):
                targets.append(
                    TargetInfo(wf.stem, "workflow", self._safe_description("workflow", wf.stem))
                )

        return targets

    def get_target_kind(self, name: str, kind: TargetKind | None = None) -> TargetKind:
        """Resolve ``name`` to ``"agent"`` or ``"workflow"`` by where its YAML lives.

        Pass ``kind`` to force one when a name exists as both. Raises
        :class:`~loom.core.exceptions.TargetResolutionError` if the (forced) kind
        is absent, if the name is ambiguous, or if it exists as neither.
        """
        is_agent = self._ws.agent(name).yaml_file.exists()
        is_workflow = self._ws.workflow_file(name).exists()

        if kind == "workflow":
            if not is_workflow:
                raise TargetResolutionError(
                    f"No workflow '{name}' found.",
                    tip=f"Add 'warp/workflows/{name}.yml', or drop kind='workflow'.",
                )
            return "workflow"
        if kind in ("agent", "bidi"):
            if not is_agent:
                raise TargetResolutionError(
                    f"No agent '{name}' found.",
                    tip=f"Create it with 'loom agent new {name}', or drop kind='{kind}'.",
                )
            return self._agent_kind(name)

        if is_agent and is_workflow:
            raise TargetResolutionError(
                f"'{name}' is both an agent and a workflow.",
                tip="Disambiguate with kind='agent' or kind='workflow'.",
            )
        if is_agent:
            return self._agent_kind(name)
        if is_workflow:
            return "workflow"
        raise TargetResolutionError(
            f"'{name}' is neither an agent nor a workflow.",
            tip=f"Create it with 'loom agent new {name}', or add 'warp/workflows/{name}.yml'.",
        )

    def _agent_kind(self, name: str) -> TargetKind:
        """Return ``"bidi"`` if the agent declares ``kind: bidi``, else ``"agent"``.

        Best-effort: a config that fails to load is reported as a plain agent
        rather than breaking discovery.
        """
        try:
            return get_agent_config(self._ws.agent(name).yaml_file).kind
        except Exception:  # noqa: BLE001 — discovery must not break on one bad config
            logger.debug("Could not read kind for agent '%s'", name, exc_info=True)
            return "agent"

    def _safe_description(self, kind: TargetKind, name: str) -> str:
        """Read a target's description best-effort (empty string on any error)."""
        try:
            if kind == "workflow":
                return get_workflow_config(self._ws.workflow_file(name)).description or ""
            return get_agent_config(self._ws.agent(name).yaml_file).description or ""
        except Exception:  # noqa: BLE001 — discovery must not break on one bad config
            logger.debug("Could not read description for %s '%s'", kind, name, exc_info=True)
            return ""

    def _hydrate(self, agent_config: AgentConfig, name: str) -> AgentConfig:
        """Resolve declarative file/dir assets to literal content.

        Keeps ``build()`` off the filesystem for declarative parts: the prompt is
        resolved to text, and declarative ``{name}.yaml`` tools are resolved to
        builtin specs. Code (tool ``.py``, ``output.py``, hooks) is *not* hydrated
        — it is resolved by import.
        """
        updates: dict[str, object] = {}

        hydrated_prompt = hydrate_prompt(
            agent_config.system_prompt, self._ws.agent_config_dir(name)
        )
        if hydrated_prompt is not agent_config.system_prompt:
            updates["system_prompt"] = hydrated_prompt

        hydrated_tools = self._hydrate_tools(agent_config.tools, name)
        if hydrated_tools is not agent_config.tools:
            updates["tools"] = hydrated_tools

        return agent_config.model_copy(update=updates) if updates else agent_config

    def _hydrate_tools(
        self, tool_defs: list[ToolConfig] | None, name: str
    ) -> list[ToolConfig] | None:
        """Resolve declarative ``{name}.yaml`` tools to builtin specs (FS probe).

        Each ``file``/``shared`` tool is probed on disk: a ``{name}.yaml`` becomes
        a builtin ``ToolConfig`` (so ``build()`` needs no filesystem for it); a
        ``{name}.py`` (code) is left untouched for the importer. ``builtin`` tools
        and missing/code tools pass through (the loader resolves/errors on those).
        """
        if not tool_defs:
            return tool_defs

        out: list[ToolConfig] = []
        changed = False
        for td in tool_defs:
            if td.source not in ("file", "shared"):
                out.append(td)
                continue

            base_dir = (
                self._ws.shared_tools_dir if td.is_shared else self._ws.agent_dir(name) / "tools"
            )
            py_file = base_dir / f"{td.name}.py"
            yaml_files = [
                p for ext in _TOOL_YAML_EXTS if (p := base_dir / f"{td.name}.{ext}").is_file()
            ]

            if not yaml_files:
                out.append(td)  # code (.py) or missing — the loader handles it
                continue
            if py_file.is_file():
                raise ToolLoadError(
                    f"Tool '{td.name}' is defined as both .py and {yaml_files[0].suffix}.",
                    tip=f"Keep one definition in {base_dir}.",
                )
            if td.params:
                raise ToolLoadError(
                    f"Tool '{td.name}' is a YAML definition and cannot take inline params.",
                    tip=f"Put its config in {yaml_files[0].name}, reference it as '- {td.name}'.",
                )

            out.append(yaml_tool_to_config(td.name, load_config(yaml_files[0])))
            changed = True

        return out if changed else tool_defs
