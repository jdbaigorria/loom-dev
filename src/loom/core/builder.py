"""
loom.core.builder — Agent construction orchestrator.

Two entry points:

- :func:`build` — the engine. Takes a *resolved* ``AgentConfig`` (+ runtime
  ``AppConfig``) and assembles a ``strands.Agent``. Dependency-inverted: it does
  no config I/O. This is the shape Loom's public ``build()`` converges on.
- :func:`build_agent` — name-based convenience wrapper. Fetches the config from a
  :class:`~loom.ports.ConfigSource` (filesystem by default) and calls :func:`build`.

Construction flow::

    build(agent_config, session, *, app_config, tools)
        ├── _select_tools()       → list[ToolConfig] (optional per-call subset)
        ├── get_model()           → Model        (Bedrock / custom passthrough)
        ├── get_prompt()          → str          (inline / file / directory)
        ├── get_tools()           → list[Tool]   (dynamic import)
        ├── get_tool_executor()   → ToolExecutor (concurrent / sequential)
        ├── get_output_class()    → Type[BaseModel] (structured output)
        ├── get_retry_strategy()  → ModelRetryStrategy
        ├── get_session_manager() → SessionManager
        ├── get_conversation_manager() → ConversationManager
        └── Agent(...)            → strands.Agent
"""

import logging
from typing import Any

from loom.adapters import strands as sx
from loom.adapters.config import FileConfigSource
from loom.adapters.strands import Agent, capabilities
from loom.core.exceptions import AgentConfigError, ToolSelectionError
from loom.ports import ConfigSource
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig
from loom.schemas.config.tool import ToolConfig
from loom.schemas.context import LoomSession

from .loaders.app import resolve_env
from .loaders.context import conversation_is_none, get_context
from .loaders.conversation import get_conversation_manager
from .loaders.hook import get_hooks
from .loaders.mcp import get_mcp_clients
from .loaders.model import get_model, is_router_model, model_log_label
from .loaders.output import get_output_class, output_target
from .loaders.plugin import get_plugins
from .loaders.prompt import get_prompt
from .loaders.retry import get_retry_strategy
from .loaders.routing import RoutingTraceHook
from .loaders.session import get_session_manager
from .loaders.storage import get_storage
from .loaders.tool import get_tools
from .loaders.tool_executor import get_tool_executor
from .paths import WorkspacePaths
from .telemetry import setup_telemetry

logger = logging.getLogger(__name__)


def _select_tools(tool_defs: list[ToolConfig] | None, names: list[str] | None) -> list[ToolConfig]:
    """Return the declared tools, optionally narrowed to ``names``.

    ``names is None`` → the full declared catalog. Otherwise every requested name
    must exist in the catalog (narrow, don't invent); an unknown name raises
    :class:`~loom.core.exceptions.ToolSelectionError`. Catalog order is preserved.
    """
    catalog = tool_defs or []
    if names is None:
        return catalog

    declared = {t.name for t in catalog}
    unknown = [n for n in names if n not in declared]
    if unknown:
        raise ToolSelectionError(
            f"Requested tool(s) not in the agent's catalog: {unknown}.",
            tip=f"Declared tools: {sorted(declared) or '(none)'}. "
            "A subset can only narrow the declared catalog, not add to it.",
        )
    wanted = set(names)
    return [t for t in catalog if t.name in wanted]


def build(
    agent_config: AgentConfig,
    session: LoomSession,
    *,
    app_config: AppConfig | None = None,
    tools: list[str] | None = None,
    paths: WorkspacePaths | None = None,
    model_params: dict[str, Any] | None = None,
) -> Agent:
    """Assemble a ``strands.Agent`` from a *resolved* ``AgentConfig``.

    The engine: it receives validated config and does no config *or* filesystem
    discovery itself (dependency inversion). Optional unconfigured parameters
    (``None``) are omitted when instantiating the agent.

    Args:
        agent_config: The agent definition (already validated, e.g. from a
            :class:`~loom.ports.ConfigSource`).
        session: Active session with ``session_id`` and ``user_id``.
        app_config: Runtime config (session/conversation/telemetry). Defaults to
            ``AppConfig()`` — the standalone convenience defaults.
        tools: Optional subset of the declared tool catalog to activate this
            build (by tool name). ``None`` activates all declared tools. A name
            not in the catalog raises ``ToolSelectionError`` (narrow, don't
            invent). MCP-server tools are not affected by this subset.
        paths: Filesystem locator for *local code/assets* (tool ``.py``,
            ``output.py``, local hooks, non-hydrated prompt files). Supplied by a
            filesystem-backed source. ``None`` when there is no local filesystem
            (e.g. a document-DB source): the config must then be fully hydrated
            and reference code by dotted path (``module:fn``), otherwise the
            relevant loader raises.
        model_params: Optional per-run overlay merged on top of the model's
            declarative constructor params (see :func:`loom.core.loaders.model.get_model`).
            The build-time channel for per-run secrets — e.g. a Bedrock
            ``boto_session`` — that must not live in the ``ConfigSource``. Also
            offered to every builtin tool's factory (see
            :func:`loom.core.loaders.tool.get_tools`), filtered to the params it
            declares — so a builtin like ``builtin.kb`` that accepts
            ``boto_session`` runs under the same per-run identity as the model,
            instead of the caller's ambient credentials.

    Returns:
        A configured ``strands.Agent`` ready to receive messages.

    Raises:
        ToolSelectionError: If ``tools`` requests an undeclared tool.
        ToolLoadError / OutputLoadError / HookLoadError: If local code is
            referenced but ``paths`` is ``None``.
        ValueError: If any loader receives an invalid configuration value.
    """
    app_config = app_config if app_config is not None else AppConfig()
    name = agent_config.name

    agent_dir = paths.agent_dir(name) if paths else None
    shared_dir = paths.shared_tools_dir if paths else None
    config_dir = paths.agent_config_dir(name) if paths else None
    hooks_dir = paths.hooks_dir if paths else None
    plugins_dir = paths.plugins_dir if paths else None

    selected_tools = _select_tools(agent_config.tools, tools)
    logger.debug(
        "Building '%s': model=%s, tools=%d/%d, prompt=%s",
        name,
        model_log_label(agent_config.model),
        len(selected_tools),
        len(agent_config.tools) if agent_config.tools else 0,
        type(agent_config.system_prompt).__name__ if agent_config.system_prompt else None,
    )

    # Tools come from local/shared Python files and/or MCP servers. MCP clients are
    # ToolProviders handed straight to the agent, which owns their open/close
    # lifecycle (started on build, stopped on ``agent.cleanup()``).
    local_tools = (
        get_tools(selected_tools, agent_dir, shared_dir, model_params) if selected_tools else []
    )
    mcp_clients = get_mcp_clients(agent_config.mcp_servers) if agent_config.mcp_servers else []
    all_tools = [*local_tools, *mcp_clients]

    if agent_config.kind == "bidi" and is_router_model(agent_config.model):
        raise AgentConfigError("model fallback is not supported when kind is 'bidi'.")

    model = get_model(agent_config.model, model_params) if agent_config.model else None
    hooks = get_hooks(agent_config.hooks, hooks_dir) if agent_config.hooks else None
    trace = None
    if sx.ModelRouter is not None and isinstance(model, sx.ModelRouter):
        trace = RoutingTraceHook()
        hooks = [*(hooks or []), trace]

    # Params shared by both kinds. Bidi reuses every loader except the model
    # (a BidiModel) and omits conversation/structured-output/retry.
    shared_params = {
        "model": model,
        "system_prompt": get_prompt(agent_config.system_prompt, base_path=config_dir)
        if agent_config.system_prompt
        else None,
        "tools": all_tools or None,
        "tool_executor": get_tool_executor(agent_config.tool_executor)
        if agent_config.tool_executor
        else None,
        "session_manager": get_session_manager(app_config.session, session.session_id)
        if app_config.session
        else None,
        "hooks": hooks,
        "storage": get_storage(
            app_config.storage,
            metadata_dir=paths.metadata_dir if paths else None,
            overlay=model_params,
        )
        if app_config.storage
        else None,
    }

    if agent_config.kind == "bidi":
        return _build_bidi(agent_config, shared_params)

    conversation = (
        agent_config.conversation
        if agent_config.conversation is not None
        else app_config.conversation
    )
    context_manager = get_context(agent_config.context) if agent_config.context is not None else None
    aux = None
    if agent_config.aux_model is not None:
        if is_router_model(agent_config.aux_model):
            raise AgentConfigError(
                "aux_model cannot be a fallback or a list.",
                tip="Point aux_model at a single profile or an inline model.",
            )
        if not capabilities.agent_accepts("aux_model"):
            raise AgentConfigError(
                "The installed Strands version does not accept aux_model.",
                tip="Requiere strands-agents >= 1.58",
            )
        aux = get_model(agent_config.aux_model, model_params)
    stateful = getattr(model, "stateful", False) is True
    if context_manager is not None and not conversation_is_none(conversation):
        raise AgentConfigError(
            "context and a conversation strategy cannot be used together.",
            tip="Set conversation: none, or remove context.",
        )
    if stateful and not conversation_is_none(conversation):
        raise AgentConfigError(
            "A stateful model cannot use a conversation strategy.",
            tip="Set conversation: none for this model.",
        )
    skip_conversation = context_manager is not None or stateful
    output_class = None
    output_prompt = None
    if agent_config.output:
        class_name, output_prompt = output_target(agent_config.output)
        output_class = get_output_class(class_name, agent_dir)
        if output_prompt is not None and not capabilities.agent_accepts("structured_output_prompt"):
            raise AgentConfigError(
                "The installed Strands version does not accept structured_output_prompt.",
                tip="Requiere strands-agents >= 1.34",
            )
    agent_only = {
        "structured_output_model": output_class,
        "structured_output_prompt": output_prompt,
        "retry_strategy": get_retry_strategy(agent_config.retry) if agent_config.retry else None,
        "conversation_manager": None
        if skip_conversation
        else (get_conversation_manager(conversation) if conversation else None),
        "plugins": get_plugins(agent_config.plugins, plugins_dir, config_dir)
        if agent_config.plugins
        else None,
        "context_manager": context_manager,
        "aux_model": aux,
    }

    clean_params = {k: v for k, v in {**shared_params, **agent_only}.items() if v is not None}
    logger.debug("Agent params resolved: %s", list(clean_params.keys()))

    agent = Agent(
        name=name,
        description=agent_config.description,
        callback_handler=None,  # forced None — clean_params filters it otherwise
        **clean_params,
    )
    if trace is not None:
        agent._loom_routing_trace = trace

    logger.info("Agent '%s' built successfully", name)
    return agent


def _build_bidi(agent_config: AgentConfig, shared_params: dict):
    """Build an experimental full-duplex ``BidiAgent`` (gated by capability).

    Reuses the shared loaders (model, prompt, tools, tool_executor, session,
    hooks) but omits conversation management, structured output and retry — none
    apply to a streaming bidi session.
    """
    if sx.BidiAgent is None:
        raise AgentConfigError(
            "The installed Strands version does not provide BidiAgent.",
            tip="Upgrade strands-agents to a version that ships strands.bidi, or set kind: agent.",
        )

    if "tool_executor" in shared_params and shared_params["tool_executor"] is not None:
        raise AgentConfigError(
            "'tool_executor' is not supported for bidi agents by the installed Strands version.",
            tip="Remove 'tool_executor' from the agent YAML (Strands >= 1.57.2 dropped it from BidiAgent).",
        )

    clean_params = {k: v for k, v in shared_params.items() if v is not None}
    logger.debug("Bidi agent params resolved: %s", list(clean_params.keys()))

    agent = sx.BidiAgent(
        name=agent_config.name,
        description=agent_config.description,
        **clean_params,
    )
    logger.info("Bidi agent '%s' built successfully", agent_config.name)
    return agent


def build_agent(
    name: str,
    session: LoomSession,
    env: str | None = None,
    *,
    source: ConfigSource | None = None,
    tools: list[str] | None = None,
    model_params: dict[str, Any] | None = None,
) -> Agent:
    """Build a ``strands.Agent`` by name, fetching config from a ``ConfigSource``.

    Name-based convenience wrapper over :func:`build`: resolves declarative config
    (``AgentConfig`` / ``AppConfig``) from ``source`` (the filesystem by default)
    and assembles the agent. Also the place runtime side-effects (telemetry setup)
    live, keeping :func:`build` a pure assembler.

    Args:
        name: Agent name. Resolves the config (and code/asset directory).
        session: Active session with ``session_id`` and ``user_id``.
        env: Environment override (e.g. ``"prod"``). If None, ``LOOM_ENV`` or
            ``"dev"``.
        source: Where declarative config comes from. Defaults to
            :class:`~loom.adapters.config.FileConfigSource`; inject an alternative
            to decouple from disk.
        tools: Optional per-call subset of the declared tool catalog (see
            :func:`build`).
        model_params: Optional per-run overlay of model constructor params (see
            :func:`build`). Used to inject per-run secrets (e.g. a Bedrock
            ``boto_session``) without persisting them in the ``ConfigSource``.

    Returns:
        A configured ``strands.Agent`` ready to receive messages.

    Raises:
        AgentNotFoundError: If no configuration exists for ``name``.
        AgentConfigError: If the config contains validation errors.
        ToolSelectionError: If ``tools`` requests an undeclared tool.
    """
    active_env = env or resolve_env()
    logger.info("Building agent '%s' (session=%s, env=%s)", name, session.session_id, active_env)

    src = source or FileConfigSource(env=active_env)
    app_config = src.get_app_config(active_env)
    setup_telemetry(app_config.telemetry)
    agent_config = src.get_agent_config(name)

    # A filesystem-backed source carries the locator for local code/assets; other
    # sources (e.g. a document DB) have none, so their configs must be hydrated and
    # reference code by dotted path.
    paths = src.workspace if isinstance(src, FileConfigSource) else None

    return build(
        agent_config,
        session,
        app_config=app_config,
        tools=tools,
        paths=paths,
        model_params=model_params,
    )
