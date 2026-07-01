"""
loom.core.workflow_builder — Build a Strands multi-agent object from a workflow YAML.

Composes existing Loom agents (each built via :func:`loom.core.builder.build_agent`)
into a Strands ``Graph`` or ``Swarm``, selected by the workflow ``type``.

Construction flow::

    build_workflow(name, session)
        ├── get_workflow_config()  → WorkflowConfig (validated YAML)
        ├── build_agent() per node/agent → strands.Agent
        └── GraphBuilder(...).build() | Swarm(...) → (MultiAgentBase, list[Agent])
"""

import logging

from loom.adapters import strands as sx
from loom.adapters.config import FileConfigSource
from loom.core.builder import build_agent
from loom.core.exceptions import WorkflowConfigError
from loom.core.loaders.app import resolve_env
from loom.ports import ConfigSource
from loom.schemas.config.workflow import GraphWorkflowConfig, SwarmWorkflowConfig
from loom.schemas.context import LoomSession
from loom.utils.loaders import import_class_from_dotted_path

logger = logging.getLogger(__name__)


def build_workflow(
    name: str,
    session: LoomSession,
    env: str | None = None,
    *,
    source: ConfigSource | None = None,
):
    """Build a Strands multi-agent object (``Graph`` or ``Swarm``) by name.

    Args:
        name: Workflow name (resolved by ``source``; the file source maps it to
            ``warp/workflows/{name}.yml``).
        session: Active session, shared by every agent node.
        env: Environment override; defaults to ``LOOM_ENV`` resolution.
        source: Where declarative config comes from. Defaults to
            :class:`~loom.adapters.config.FileConfigSource`; the same source is
            threaded to every node's :func:`build_agent`, so a non-filesystem
            deployment serves the whole workflow without touching disk.

    Returns:
        A tuple ``(workflow, node_agents)`` where ``workflow`` is a Strands
        ``MultiAgentBase`` ready to invoke, and ``node_agents`` is the list of
        built agents. ``Graph``/``Swarm`` have no ``cleanup()`` of their own, so
        the caller cleans up each node agent (closing its MCP connections) after
        execution.

    Raises:
        WorkflowNotFoundError: If the workflow does not exist.
        WorkflowConfigError: If the config is invalid or Strands lacks the primitive.
        AgentNotFoundError: If a referenced agent does not exist.
    """
    active_env = env or resolve_env()
    src = source or FileConfigSource(env=active_env)
    config = src.get_workflow_config(name)
    logger.info("Building workflow '%s' (type=%s, env=%s)", name, config.type, active_env)

    if isinstance(config, GraphWorkflowConfig):
        return _build_graph(config, session, active_env, src)
    return _build_swarm(config, session, active_env, src)


def _build_graph(
    config: GraphWorkflowConfig, session: LoomSession, env: str, source: ConfigSource
):
    """Assemble a Strands ``Graph`` from a graph workflow config."""
    if sx.GraphBuilder is None:
        raise WorkflowConfigError(
            "The installed Strands version does not provide graph orchestration.",
            tip="Upgrade strands-agents to a version that ships strands.multiagent.GraphBuilder.",
        )

    builder = sx.GraphBuilder()
    built_agents: list = []
    for node_id, node in config.nodes.items():
        agent = build_agent(node.agent, session, env, source=source)
        built_agents.append(agent)
        builder.add_node(agent, node_id)

    for edge in config.edges:
        if edge.condition:
            condition = import_class_from_dotted_path(edge.condition)
            builder.add_edge(edge.from_node, edge.to_node, condition=condition)
        else:
            builder.add_edge(edge.from_node, edge.to_node)

    if config.entry_point is not None:
        builder.set_entry_point(config.entry_point)

    logger.debug("Graph built: %d node(s), %d edge(s)", len(config.nodes), len(config.edges))
    return builder.build(), built_agents


def _build_swarm(
    config: SwarmWorkflowConfig, session: LoomSession, env: str, source: ConfigSource
):
    """Assemble a Strands ``Swarm`` from a swarm workflow config."""
    if sx.Swarm is None:
        raise WorkflowConfigError(
            "The installed Strands version does not provide swarm orchestration.",
            tip="Upgrade strands-agents to a version that ships strands.multiagent.Swarm.",
        )

    # dict.fromkeys preserves order and de-duplicates agent names.
    agents = {
        agent_name: build_agent(agent_name, session, env, source=source)
        for agent_name in dict.fromkeys(config.agents)
    }
    entry = agents[config.entry_point] if config.entry_point is not None else None

    logger.debug("Swarm built: %d agent(s)", len(agents))
    return (
        sx.Swarm(
            list(agents.values()),
            entry_point=entry,
            max_handoffs=config.max_handoffs,
            max_iterations=config.max_iterations,
        ),
        list(agents.values()),
    )
