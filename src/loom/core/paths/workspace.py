"""Workspace path composition.

``WorkspacePaths`` is the resolved map of a Loom project: it composes
``MetadataPaths`` (``.loom/``) and per-agent ``AgentPaths``. Builders only compose
``pathlib.Path`` values; name normalization lives in ``.naming`` and existence
checks in the ``resolve_existing_*`` helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loom.config.loom_config import get_loom_config
from loom.core.exceptions import AgentNotFoundError
from loom.schemas.config.loom import LoomConfig
from loom.utils.loaders import get_project_root

from .naming import normalize_agent_name


@dataclass(frozen=True)
class MetadataPaths:
    """Paths under the hidden metadata directory (``.loom/``)."""

    root: Path

    @property
    def stats_dir(self) -> Path:
        return self.root / "stats"

    @property
    def sessions_dir(self) -> Path:
        return self.root / "sessions"

    def agent_stats_file(self, agent_name: str) -> Path:
        return self.stats_dir / f"{agent_name}.jsonl"


@dataclass(frozen=True)
class AgentPaths:
    """Paths relative to one agent root directory ``.../agents/{name}/``."""

    root: Path

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def yaml_file(self) -> Path:
        return self.config_dir / f"{self.root.name}.yml"

    @property
    def prompt_file(self) -> Path:
        return self.config_dir / "prompt.md"

    @property
    def prompts_dir(self) -> Path:
        return self.config_dir / "prompts"

    @property
    def eval_dir(self) -> Path:
        return self.root / "evals"

    @property
    def eval_file(self) -> Path:
        return self.eval_dir / "evals.yml"

    @property
    def eval_results_dir(self) -> Path:
        return self.eval_dir / "results"


@dataclass(frozen=True)
class WorkspacePaths:
    """Resolved paths for one Loom project root and workspace folder name."""

    project_root: Path
    workspace_name: str

    @property
    def root(self) -> Path:
        """Alias for ``project_root`` (compatibility with older call sites)."""
        return self.project_root

    @property
    def base_dir(self) -> Path:
        return self.project_root / self.workspace_name

    @property
    def loom_file(self) -> Path:
        return self.project_root / "loom.toml"

    @property
    def metadata_dir(self) -> Path:
        return self.project_root / ".loom"

    @property
    def metadata(self) -> MetadataPaths:
        return MetadataPaths(self.metadata_dir)

    @property
    def agents_dir(self) -> Path:
        return self.base_dir / "agents"

    @property
    def app_dir(self) -> Path:
        """Application YAML directory (``warp/config/``)."""
        return self.base_dir / "config"

    @property
    def config_file(self) -> Path:
        """Path to ``app.yml``."""
        return self.app_dir / "app.yml"

    @property
    def profiles_file(self) -> Path:
        """Opinionated presets file (``warp/config/profiles.toml``)."""
        return self.app_dir / "profiles.toml"

    @property
    def hooks_dir(self) -> Path:
        return self.base_dir / "hooks"

    @property
    def workflows_dir(self) -> Path:
        """Multi-agent workflow definitions (``warp/workflows/``)."""
        return self.base_dir / "workflows"

    def workflow_file(self, name: str) -> Path:
        """Workflow definition YAML (``warp/workflows/{name}.yml``)."""
        return self.workflows_dir / f"{normalize_agent_name(name)}.yml"

    @property
    def shared_tools_dir(self) -> Path:
        return self.agents_dir / "tools"

    def agent(self, name: str) -> AgentPaths:
        """Paths for one agent; ``name`` is normalized."""
        normalized = normalize_agent_name(name)
        return AgentPaths(self.agents_dir / normalized)

    def agent_dir(self, name: str) -> Path:
        """Agent root directory (``warp/agents/{name}/``)."""
        return self.agent(name).root

    def agent_config_dir(self, name: str) -> Path:
        return self.agent(name).config_dir

    def agent_prompt_file(self, name: str) -> Path:
        return self.agent(name).prompt_file

    def agent_prompts_dir(self, name: str) -> Path:
        return self.agent(name).prompts_dir

    def eval_dir(self, name: str) -> Path:
        return self.agent(name).eval_dir

    def eval_results_dir(self, name: str) -> Path:
        return self.agent(name).eval_results_dir

    def eval_file(self, name: str) -> Path:
        """Evaluation definition YAML for an agent (``evals/evals.yml``)."""
        return self.agent(name).eval_file

    def agent_stats_file(self, name: str) -> Path:
        return self.metadata.agent_stats_file(normalize_agent_name(name))

    def resolve_agent_yaml(self, name: str) -> Path:
        """Return agent YAML path, raising ``AgentNotFoundError`` if missing."""
        return resolve_existing_agent_yaml(self, name)


def resolve_existing_agent_yaml(ws: WorkspacePaths, name: str) -> Path:
    """Return the agent config YAML path, raising if the file does not exist.

    Raises:
        AgentNotFoundError: If the YAML file is missing.
    """
    yaml_path = ws.agent(name).yaml_file
    if not yaml_path.exists():
        raise AgentNotFoundError(name)
    return yaml_path


def resolve_existing_workflow_yaml(ws: WorkspacePaths, name: str) -> Path:
    """Return the workflow YAML path, raising if the file does not exist.

    Raises:
        WorkflowNotFoundError: If the YAML file is missing.
    """
    from loom.core.exceptions import WorkflowNotFoundError

    yaml_path = ws.workflow_file(name)
    if not yaml_path.exists():
        raise WorkflowNotFoundError(name)
    return yaml_path


def build_workspace_paths(
    *,
    project_root: Path | None = None,
    config: LoomConfig | None = None,
) -> WorkspacePaths:
    """Build a ``WorkspacePaths`` from project root and ``loom.toml`` config.

    Args:
        project_root: Project root; defaults to ``get_project_root()``.
        config: Parsed ``LoomConfig``; defaults to ``get_loom_config()``.

    Returns:
        Frozen workspace path bundle.
    """
    root = project_root if project_root is not None else get_project_root()
    cfg = config if config is not None else get_loom_config()
    return WorkspacePaths(project_root=root, workspace_name=cfg.workspace_name)
