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
ModelRetryStrategy = resolve("strands.ModelRetryStrategy")
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

# --- Bidirectional -------------------------------------------------------------
# Optional: full-duplex voice/streaming agent. Gated by capabilities; the builder
# raises a friendly error when the installed Strands lacks it.
BidiAgent = resolve(
    "strands.bidi.BidiAgent",
    "strands.bidi.agent.BidiAgent",
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

# --- SDK 1.62 surfaces (optional; loaders raise AgentConfigError when absent) --
Plugin = resolve("strands.plugins.Plugin", "strands.Plugin", optional=True)
InterventionHandler = resolve("strands.interventions.handler.InterventionHandler", optional=True)
MemoryManager = resolve("strands.memory.MemoryManager", optional=True)
FileMemoryStore = resolve("strands.vended_memory_stores.FileMemoryStore", optional=True)
BedrockKnowledgeBaseStore = resolve(
    "strands.vended_memory_stores.bedrock_knowledge_base.BedrockKnowledgeBaseStore",
    optional=True,
)
AgentSkills = resolve("strands.vended_plugins.skills.AgentSkills", optional=True)
ContextOffloader = resolve(
    "strands.vended_plugins.context_offloader.ContextOffloader", optional=True
)
GoalLoop = resolve("strands.vended_plugins.goal.GoalLoop", optional=True)
HumanInTheLoop = resolve("strands.vended_interventions.HumanInTheLoop", optional=True)
CedarAuthorization = resolve("strands.vended_interventions.cedar.CedarAuthorization", optional=True)
Sandbox = resolve("strands.sandbox.Sandbox", optional=True)
DockerSandbox = resolve("strands.sandbox.docker.DockerSandbox", optional=True)
SshSandbox = resolve("strands.sandbox.ssh.SshSandbox", optional=True)
Storage = resolve("strands.storage.Storage", optional=True)
LocalFileStorage = resolve("strands.storage.LocalFileStorage", optional=True)
S3Storage = resolve("strands.storage.S3Storage", optional=True)
InMemoryStorage = resolve("strands.storage.InMemoryStorage", optional=True)
ModelRouter = resolve(
    "strands.models.routing.ModelRouter", "strands.models.ModelRouter", optional=True
)
RoutingCandidate = resolve("strands.models.routing.RoutingCandidate", optional=True)
FallbackStrategy = resolve("strands.models.routing.FallbackStrategy", optional=True)
ClassifierStrategy = resolve("strands.models.routing.ClassifierStrategy", optional=True)
AfterModelCallEvent = resolve(
    "strands.hooks.AfterModelCallEvent",
    "strands.hooks.events.AfterModelCallEvent",
    optional=True,
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
    "AfterModelCallEvent",
    "AfterToolCallEvent",
    "Agent",
    "AgentSkills",
    "AgentResult",
    "BedrockKnowledgeBaseStore",
    "BedrockModel",
    "BidiAgent",
    "CedarAuthorization",
    "ClassifierStrategy",
    "ContextOffloader",
    "BeforeInvocationEvent",
    "BeforeToolCallEvent",
    "ConcurrentToolExecutor",
    "ConversationManager",
    "DecoratedFunctionTool",
    "DockerSandbox",
    "FallbackStrategy",
    "FileMemoryStore",
    "FileSessionManager",
    "GoalLoop",
    "HumanInTheLoop",
    "InMemoryStorage",
    "InterventionHandler",
    "LocalFileStorage",
    "HookProvider",
    "HookRegistry",
    "LoomStrandsCompatError",
    "GraphBuilder",
    "MCPClient",
    "MemoryManager",
    "Messages",
    "Model",
    "ModelRouter",
    "ModelRetryStrategy",
    "MultiAgentResult",
    "NullConversationManager",
    "Plugin",
    "RoutingCandidate",
    "S3SessionManager",
    "S3Storage",
    "Sandbox",
    "SessionManager",
    "SequentialToolExecutor",
    "SshSandbox",
    "Storage",
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
