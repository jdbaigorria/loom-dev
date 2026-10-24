"""Example 09 — Strands 1.62 fields, built offline.

The YAML next to this file declares plugins, context, memory, interventions,
background tasks, checkpointing, aux_model, storage, a Docker sandbox, and
trace attributes. The model is ``loom.testing.MockModel``, so the build does
not call Bedrock.

Run from the repo root:

    python -m examples.09_sdk_features.example
"""

from pathlib import Path

from omegaconf import OmegaConf

from loom.core.builder import build
from loom.core.paths import WorkspacePaths
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig
from loom.schemas.context import LoomSession

_HERE = Path(__file__).resolve().parent


def load_configs() -> tuple[AgentConfig, AppConfig]:
    """Read ``assistant.yml`` and ``app.yml`` beside this module."""
    agent = AgentConfig.model_validate(
        OmegaConf.to_container(OmegaConf.load(_HERE / "assistant.yml"), resolve=True)
    )
    app = AppConfig.model_validate(
        OmegaConf.to_container(OmegaConf.load(_HERE / "app.yml"), resolve=True)
    )
    return agent, app


def build_features(project_root: Path) -> object:
    """Build the example agent. ``project_root`` is where ``.loom/`` is created."""
    agent_cfg, app_cfg = load_configs()
    paths = WorkspacePaths(project_root=project_root, workspace_name="warp")
    return build(
        agent_cfg,
        LoomSession(session_id="session-001", user_id="ada"),
        app_config=app_cfg,
        paths=paths,
    )


def main() -> None:
    agent = build_features(Path.cwd())
    print(f"Built: {type(agent).__name__}")
    print(f"Plugins: {sorted(agent._plugin_registry._plugins)}")
    print(f"Memory: {agent.memory_manager._stores[0].description}")
    print(f"Trace: {agent.trace_attributes}")
    agent.cleanup()


if __name__ == "__main__":
    main()
