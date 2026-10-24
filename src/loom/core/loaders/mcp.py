"""
loom.core.loaders.mcp — Build declarative MCP servers as Strands tool providers.

For each ``MCPServerConfig`` declared on an agent, builds a Strands ``MCPClient``
over the right transport (stdio for local processes, http/sse for remote). A
``MCPClient`` is a Strands ``ToolProvider``: it is handed *unstarted* straight to
``Agent(tools=[...])`` and the agent's tool registry owns its whole lifecycle —
it opens the connection when the agent is built (``add_consumer`` + ``load_tools``)
and closes it on ``agent.cleanup()`` (``remove_consumer``, ref-counted). Loom no
longer starts, lists, or closes MCP connections itself.

Transport for ``stdio`` and ``sse`` is built in ``loom.adapters.strands.mcp``.
``http`` is built by ``MCPClient(url=...)``, which owns the mcp 1.x/2.x differences.
"""

import logging

from loom.adapters import strands as sx
from loom.adapters.strands import mcp as sx_mcp
from loom.core.exceptions import AgentConfigError
from loom.schemas.config.mcp import MCPServerConfig, StdioMCPServer

logger = logging.getLogger(__name__)


def _build_client(server: MCPServerConfig):
    """Build one unstarted ``MCPClient`` for ``server``."""
    if isinstance(server, StdioMCPServer):
        transport = sx_mcp.stdio_transport(server.command, server.args, server.env)
        return sx.MCPClient(transport, prefix=server.name)
    if server.transport == "http":
        try:
            return sx.MCPClient(url=server.url, headers=server.headers, prefix=server.name)
        except ValueError as exc:
            raise AgentConfigError(
                f"Invalid MCP HTTP URL for server '{server.name}': {server.url}",
                tip="Use an http:// or https:// URL.",
            ) from exc
    transport = sx_mcp.sse_transport(server.url, server.headers)
    return sx.MCPClient(transport, prefix=server.name)


def get_mcp_clients(servers: list[MCPServerConfig]) -> list:
    """Build one ``MCPClient`` per declared server, ready for ``Agent(tools=...)``.

    The clients are returned **unstarted**. Because ``MCPClient`` is a Strands
    ``ToolProvider``, the agent's tool registry starts each connection when the
    agent is built and stops it on ``agent.cleanup()`` — Loom does not manage the
    connection lifecycle.

    Args:
        servers: MCP server configs from the agent YAML.

    Returns:
        The list of ``MCPClient`` tool providers to splice into the agent's tools.

    Raises:
        AgentConfigError: If the installed Strands lacks MCP support.
    """
    if sx.MCPClient is None:
        raise AgentConfigError(
            "The installed Strands version does not provide MCP support.",
            tip="Upgrade strands-agents to a version that ships strands.tools.mcp, "
            "or remove 'mcp_servers' from the agent YAML.",
        )

    clients = [_build_client(server) for server in servers]
    logger.info("Prepared %d MCP client(s) as tool providers", len(clients))
    return clients
