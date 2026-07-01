"""loom.adapters.strands — Single import surface for the Strands SDK.

Every Strands symbol Loom uses is resolved here once, via :func:`resolve` with
version-tolerant fallback paths. The rest of Loom imports from this module:

    from loom.adapters.strands import Agent, BedrockModel, HookProvider

instead of reaching into ``strands.*`` submodules directly. A ruff
``banned-api`` rule enforces that ``strands`` is imported nowhere else.

Optional model providers (OpenAI, Gemini) resolve to ``None`` when their extra
is not installed; callers should check and raise a friendly error.
"""

from __future__ import annotations

from ._resolve import LoomStrandsCompatError, is_available, resolve

# --- Core agent surface --------------------------------------------------------
Agent = resolve("strands.Agent", "strands.agent.agent.Agent")
tool = resolve("strands.tool", "strands.tools.decorator.tool")
ToolContext = resolve("strands.ToolContext", "strands.tools.context.ToolContext")
ModelRetryStrategy = resolve(
    "strands.ModelRetryStrategy",
    "strands.agent.model_retry.ModelRetryStrategy",
)
AgentResult = resolve(
    "strands.agent.agent_result.AgentResult",
    "strands.agent.AgentResult",
)
DecoratedFunctionTool = resolve(
    "strands.tools.decorator.DecoratedFunctionTool",
    "strands.tools.DecoratedFunctionTool",
)

# --- Models --------------------------------------------------------------------
# Bedrock is the one typed/tested provider. Every other provider (OpenAI, Gemini,
# LiteLLM, Ollama, custom) is reached via the `custom` passthrough, which resolves
# an arbitrary dotted import_path through resolve() — so no per-provider symbol is
# pinned here.
Model = resolve("strands.models.Model", "strands.models.model.Model")
BedrockModel = resolve("strands.models.bedrock.BedrockModel", "strands.models.BedrockModel")

# --- Conversation managers -----------------------------------------------------
ConversationManager = resolve(
    "strands.agent.conversation_manager.ConversationManager",
    "strands.agent.conversation_manager.conversation_manager.ConversationManager",
)
NullConversationManager = resolve(
    "strands.agent.conversation_manager.NullConversationManager",
    "strands.agent.conversation_manager.null_conversation_manager.NullConversationManager",
)
SlidingWindowConversationManager = resolve(
    "strands.agent.conversation_manager.SlidingWindowConversationManager",
    "strands.agent.conversation_manager.sliding_window_conversation_manager.SlidingWindowConversationManager",
)
SummarizingConversationManager = resolve(
    "strands.agent.conversation_manager.SummarizingConversationManager",
    "strands.agent.conversation_manager.summarizing_conversation_manager.SummarizingConversationManager",
)

# --- Session managers ----------------------------------------------------------
SessionManager = resolve(
    "strands.session.SessionManager",
    "strands.session.session_manager.SessionManager",
)
FileSessionManager = resolve(
    "strands.session.file_session_manager.FileSessionManager",
    "strands.session.FileSessionManager",
)
S3SessionManager = resolve(
    "strands.session.s3_session_manager.S3SessionManager",
    "strands.session.S3SessionManager",
)

# --- Hooks ---------------------------------------------------------------------
HookProvider = resolve("strands.hooks.HookProvider", "strands.hooks.registry.HookProvider")
HookRegistry = resolve("strands.hooks.HookRegistry", "strands.hooks.registry.HookRegistry")
BeforeInvocationEvent = resolve(
    "strands.hooks.BeforeInvocationEvent",
    "strands.hooks.events.BeforeInvocationEvent",
)
AfterInvocationEvent = resolve(
    "strands.hooks.AfterInvocationEvent",
    "strands.hooks.events.AfterInvocationEvent",
)
BeforeToolCallEvent = resolve(
    "strands.hooks.BeforeToolCallEvent",
    "strands.hooks.events.BeforeToolCallEvent",
)
AfterToolCallEvent = resolve(
    "strands.hooks.AfterToolCallEvent",
    "strands.hooks.events.AfterToolCallEvent",
)

# --- Multi-agent orchestration -------------------------------------------------
# Optional: older Strands versions may not ship these. The workflow builder checks
# for None (via capabilities) and raises a friendly error instead of crashing the
# whole package at import time.
Swarm = resolve("strands.multiagent.Swarm", "strands.multiagent.swarm.Swarm", optional=True)
GraphBuilder = resolve(
    "strands.multiagent.GraphBuilder", "strands.multiagent.graph.GraphBuilder", optional=True
)
MultiAgentResult = resolve(
    "strands.multiagent.base.MultiAgentResult",
    "strands.multiagent.MultiAgentResult",
    optional=True,
)

# --- Bidirectional (experimental) ----------------------------------------------
# Optional + EXPERIMENTAL: full-duplex voice/streaming agent. Gated by capabilities;
# the builder raises a friendly error when the installed Strands lacks it.
BidiAgent = resolve(
    "strands.experimental.bidi.BidiAgent",
    "strands.experimental.bidi.agent.BidiAgent",
    optional=True,
)

# --- Tool executors ------------------------------------------------------------
# Optional: pluggable tool execution strategy (concurrent/sequential). Gated by
# capabilities; the loader raises a friendly error if a Strands build lacks them.
ConcurrentToolExecutor = resolve(
    "strands.tools.executors.ConcurrentToolExecutor",
    "strands.tools.executors.concurrent.ConcurrentToolExecutor",
    optional=True,
)
SequentialToolExecutor = resolve(
    "strands.tools.executors.SequentialToolExecutor",
    "strands.tools.executors.sequential.SequentialToolExecutor",
    optional=True,
)

# --- MCP (Model Context Protocol) ----------------------------------------------
# Optional: connect MCP servers as tools. Gated by capabilities; the loader raises
# a friendly error when absent.
MCPClient = resolve(
    "strands.tools.mcp.MCPClient", "strands.tools.mcp.mcp_client.MCPClient", optional=True
)

# --- Telemetry -----------------------------------------------------------------
# Optional: OpenTelemetry setup helper. Gated by capabilities; telemetry setup is
# a no-op (with a warning) when absent.
StrandsTelemetry = resolve(
    "strands.telemetry.StrandsTelemetry",
    "strands.telemetry.config.StrandsTelemetry",
    optional=True,
)

# --- Types ---------------------------------------------------------------------
SystemContentBlock = resolve("strands.types.content.SystemContentBlock")
Messages = resolve("strands.types.content.Messages")
StreamEvent = resolve("strands.types.streaming.StreamEvent")
ToolChoice = resolve("strands.types.tools.ToolChoice")
ToolSpec = resolve("strands.types.tools.ToolSpec")
ToolResult = resolve("strands.types.tools.ToolResult")
ToolResultContent = resolve("strands.types.tools.ToolResultContent")

__all__ = [
    "AfterInvocationEvent",
    "AfterToolCallEvent",
    "Agent",
    "AgentResult",
    "BedrockModel",
    "BidiAgent",
    "BeforeInvocationEvent",
    "BeforeToolCallEvent",
    "ConcurrentToolExecutor",
    "ConversationManager",
    "DecoratedFunctionTool",
    "FileSessionManager",
    "HookProvider",
    "HookRegistry",
    "LoomStrandsCompatError",
    "GraphBuilder",
    "Messages",
    "Model",
    "MCPClient",
    "ModelRetryStrategy",
    "MultiAgentResult",
    "NullConversationManager",
    "S3SessionManager",
    "SessionManager",
    "SequentialToolExecutor",
    "SlidingWindowConversationManager",
    "StrandsTelemetry",
    "StreamEvent",
    "Swarm",
    "SummarizingConversationManager",
    "SystemContentBlock",
    "ToolChoice",
    "ToolContext",
    "ToolResult",
    "ToolResultContent",
    "ToolSpec",
    "is_available",
    "resolve",
    "tool",
]
