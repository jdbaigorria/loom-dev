"""loom.dev — Dev-only executor: build an agent and run it once.

Loom is a *build* library; production execution belongs to the backend, which
calls the built ``strands.Agent`` natively. This module is the one sanctioned
executor inside Loom and it **never ships to prod** — it backs the eval runner
and the ``loom agent run`` / ``loom agent dev`` CLI.

It builds the agent via :func:`~loom.core.builder.build_agent`, runs a single
turn (forwarding ``extras`` as native Strands ``invocation_state``), records the
dev stats line, and tears down MCP connections. No ambient context, no contextvar
— tools read identity/extras through ``tool_context.invocation_state``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from loom.adapters.config import FileConfigSource
from loom.adapters.strands import Agent
from loom.core.builder import build_agent
from loom.core.exceptions import LoomError
from loom.core.loaders.app import resolve_env
from loom.core.loaders.model import declared_model_id
from loom.core.response import estimate_tokens, run_and_record
from loom.core.workflow_builder import build_workflow
from loom.schemas.context import LoomSession
from loom.schemas.response import AgentResponse, AgentResponseMetadata
from loom.schemas.target import TargetKind

logger = logging.getLogger(__name__)


def _resolve_kind(name: str, kind: TargetKind | None, env: str | None) -> TargetKind:
    """Resolve a target's kind through the filesystem ``ConfigSource`` (dev path)."""
    return FileConfigSource(env=env or resolve_env()).get_target_kind(name, kind)


@dataclass
class DevAgent:
    """A built agent plus the small metadata the dev executor needs to run + record.

    Holds the live ``strands.Agent`` and the values stats recording wants
    (``model_id``, ``system_prompt_tokens``). The interactive CLI keeps one of
    these across turns (so conversation history lives in memory even with session
    persistence off); :func:`run_dev` builds one per call.
    """

    agent: Agent
    model_id: str | None
    system_prompt_tokens: int
    name: str


@dataclass
class DevRun:
    """Outcome of a single dev execution: the shaped response plus the built agent.

    ``agent`` is exposed so dev tooling (e.g. the eval runner) can inspect the
    post-run message history / tool trajectory. Production code never needs it —
    it calls Strands directly.
    """

    response: AgentResponse
    agent: Agent


def build_dev_agent(name: str, session: LoomSession, *, env: str | None = None) -> DevAgent:
    """Build agent ``name`` and bundle the metadata the dev executor records.

    Shared by :func:`run_dev` (one-shot) and the interactive ``loom agent run`` /
    ``loom agent dev`` loops (which build once and call the agent per turn).
    """
    active_env = env or resolve_env()
    src = FileConfigSource(env=active_env)
    agent_config = src.get_agent_config(name)
    model_id = declared_model_id(agent_config.model)
    agent = build_agent(name, session, active_env, source=src)
    return DevAgent(
        agent=agent,
        model_id=model_id,
        system_prompt_tokens=estimate_tokens(agent.system_prompt or ""),
        name=name,
    )


def run_turn(
    dev: DevAgent,
    query: Any,
    session: LoomSession,
    *,
    extras: dict[str, Any] | None = None,
) -> tuple[AgentResponse, bool]:
    """Run one turn on an already-built :class:`DevAgent`; shape + record the result.

    Does not touch MCP lifecycle — the caller owns that (the REPL keeps the agent
    alive across turns; :func:`run_dev` tears it down once).

    Returns ``(response, interrupted)``.
    """
    return run_and_record(
        dev.agent,
        query,
        session,
        model_id=dev.model_id,
        name=dev.name,
        system_prompt_tokens=dev.system_prompt_tokens,
        invocation_state=extras or {},
    )


def run_dev(
    name: str,
    query: Any,
    session: LoomSession,
    *,
    extras: dict[str, Any] | None = None,
    env: str | None = None,
    kind: TargetKind | None = None,
) -> DevRun:
    """Build target ``name`` and run a single turn — the dev-only execution path.

    Polymorphic over the target kind (the role the old ``loom.invoke`` played):
    an **agent** runs one turn via :func:`run_turn`; a **workflow** (Graph/Swarm)
    runs once and its terminal text + aggregate metrics are shaped to the same
    :class:`~loom.schemas.response.AgentResponse`.

    Args:
        name: Agent or workflow name (resolved by where its YAML lives).
        query: The input Strands expects — a string or a list of content blocks.
        session: Identity (``session_id``/``user_id``) for this run.
        extras: Free-form context forwarded as native ``invocation_state``; tools
            read it via ``tool_context.invocation_state`` (agent path).
        env: Environment override (e.g. ``"prod"``); defaults to ``LOOM_ENV``/``dev``.
        kind: Optional ``"agent"``/``"workflow"`` override when a name is both.

    Returns:
        A :class:`DevRun` with the shaped ``response`` and the built target
        (``agent`` for an agent, the Graph/Swarm object for a workflow).
    """
    resolved = _resolve_kind(name, kind, env)
    if resolved == "bidi":
        raise LoomError(
            f"'{name}' is a bidi (full-duplex) agent — run_dev is one-shot only.",
            tip="Build it with build_agent() and drive it through the harness's "
            "full-duplex stream (send/receive), not run_dev.",
        )
    if resolved == "workflow":
        return _run_workflow_dev(name, query, session, env=env)

    dev = build_dev_agent(name, session, env=env)

    logger.info("run_dev: agent=%s session=%s", name, session.session_id)
    try:
        response, _interrupted = run_turn(dev, query, session, extras=extras)
    finally:
        # Closes any MCP connections the agent opened (no-op if it has none).
        dev.agent.cleanup()

    return DevRun(response=response, agent=dev.agent)


def _run_workflow_dev(name: str, query: Any, session: LoomSession, *, env: str | None) -> DevRun:
    """Build and run a multi-agent workflow once, shaping its result like an agent's."""
    logger.info("run_dev: workflow=%s session=%s", name, session.session_id)
    workflow, node_agents = build_workflow(name, session, env or resolve_env())
    try:
        result = workflow(query)
    finally:
        # Graph/Swarm have no cleanup() of their own — tear down each node agent
        # (closing its MCP connections).
        for agent in node_agents:
            agent.cleanup()
    response = AgentResponse(
        answer=_final_text(result), metadata=_workflow_metadata(result, session)
    )
    return DevRun(response=response, agent=workflow)


# --- Workflow result shaping (pure; was LoomWorkflow's private helpers) --------


def _workflow_metadata(result: Any, session: LoomSession) -> AgentResponseMetadata:
    """Map a Strands ``MultiAgentResult`` to ``AgentResponseMetadata``."""
    usage = getattr(result, "accumulated_usage", {}) or {}
    return AgentResponseMetadata(
        session_id=session.session_id,
        user_id=session.user_id,
        user_msg_idx=0,
        assistant_msg_idx=0,
        input_tokens=usage.get("inputTokens", 0),
        output_tokens=usage.get("outputTokens", 0),
        total_tokens=usage.get("totalTokens", 0),
        response_time_ms=float(getattr(result, "execution_time", 0) or 0),
        model_id=None,
        tool_calls=[],
        raw_metrics={
            "status": str(getattr(result, "status", "")),
            "execution_count": getattr(result, "execution_count", 0),
            "nodes": list(getattr(result, "results", {}) or {}),
        },
    )


def _final_text(result: Any) -> str:
    """Extract the terminal answer text from a ``MultiAgentResult``.

    Walks node results from last-executed to first and returns the first
    non-empty agent text, recursing into nested multi-agent results.
    """
    results = getattr(result, "results", None)
    if not results:
        return ""
    for node_result in reversed(list(results.values())):
        inner = getattr(node_result, "result", node_result)
        text = _agent_text(inner)
        if text:
            return text
    return ""


def _agent_text(obj: Any) -> str:
    """Pull ``message.content[0].text`` from an AgentResult, or recurse if nested."""
    message = getattr(obj, "message", None)
    if isinstance(message, dict):
        content = message.get("content") or []
        if content and isinstance(content[0], dict):
            return content[0].get("text", "") or ""
    if getattr(obj, "results", None):
        return _final_text(obj)
    return ""
