"""loom — Declarative AI agent framework built on Strands Agents.

Loom is a **build** library: it turns a declarative definition into a native
Strands object (``Agent`` / ``Graph`` / ``Swarm``) and hands it back. Execution
belongs to the caller — the backend invokes the built object through Strands
natively. The only executor Loom ships is :func:`loom.dev.run_dev`, which is
**dev-only** (it backs the eval runner and the CLI) and never runs in prod.

The names re-exported here are Loom's **public API** and the stability boundary:
once out of alpha they follow semantic versioning. Everything else
(``loom.core``, ``loom.adapters``, ``loom.schemas.config``, loaders, services,
CLI internals) is internal and may change without a major bump.

Public surface::

    from loom import (
        build,            # engine: build(agent_config, session, ...) -> strands.Agent
        build_agent,      # by name: build_agent(name, session) -> strands.Agent
        build_workflow,   # by name: build_workflow(name, session) -> (Graph/Swarm, node_agents)
        discover,         # catalog: discover() -> list[TargetInfo(name, kind, desc)]
        TargetInfo,       # a buildable target (name, kind, description)
        LoomEvals,        # evaluation runner (lazy — needs the [evals] extra)
        LoomSession,      # execution identity (session_id, user_id)
    )
    from loom.dev import run_dev   # dev-only executor (agent or workflow)
    from loom.errors import LoomError, AgentNotFoundError, ...   # public exception surface
    from loom.ports import ConfigSource                          # config-source seam (inject a source)

The build_agent / build_workflow split is the lingua franca with the harness: Loom
hands back native Strands runnables (``Agent`` / ``Graph`` / ``Swarm`` / ``BidiAgent``)
and the harness drives + normalizes them. ``run_dev`` is dev-only.

Selection/routing across targets and request/response DTOs are **not** Loom's
job — that is execution-time policy for the backend/harness over the catalog.

Provider configuration: Bedrock is the typed, tested path; every other provider
(OpenAI, Gemini, LiteLLM, Ollama, custom) is reached through the generic
``provider: custom`` passthrough (``import_path`` + ``params``).
"""

from typing import TYPE_CHECKING

from loom.core.builder import build, build_agent
from loom.core.workflow_builder import build_workflow
from loom.schemas.context import LoomSession
from loom.schemas.target import TargetInfo

if TYPE_CHECKING:
    from loom.loom_evals import LoomEvals
    from loom.ports import ConfigSource

__all__ = [
    "LoomEvals",
    "LoomSession",
    "TargetInfo",
    "build",
    "build_agent",
    "build_workflow",
    "discover",
]


def discover(source: "ConfigSource | None" = None) -> list[TargetInfo]:
    """Return the catalog of buildable targets.

    The name-based discovery entry point: ``[TargetInfo(name, kind, description)]``
    for every agent and workflow the source knows. The backend/harness uses this to
    learn *what exists* and *of which kind* without importing agent code. ``source``
    defaults to :class:`~loom.adapters.config.FileConfigSource` (the ``warp/``
    folder); a non-filesystem deployment passes its own source to list from there.
    """
    if source is None:
        from loom.adapters.config import FileConfigSource

        source = FileConfigSource()

    return source.list_targets()


def __getattr__(name: str) -> object:
    """Lazily expose ``LoomEvals`` so ``import loom`` does not pull in the evals
    stack (``strands_evals``), which lives behind the optional ``evals`` extra."""
    if name == "LoomEvals":
        from loom.loom_evals import LoomEvals

        return LoomEvals
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
