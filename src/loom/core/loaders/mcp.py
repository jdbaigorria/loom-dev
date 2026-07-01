"""
loom.core.loaders.mcp — Build declarative MCP servers as Strands tool providers.

For each ``MCPServerConfig`` declared on an agent, builds a Strands ``MCPClient``
over the right transport (stdio for local processes, http/sse for remote). A
``MCPClient`` is a Strands ``ToolProvider``: it is handed *unstarted* straight to
``Agent(tools=[...])`` and the agent's tool registry owns its whole lifecycle —
it opens the connection when the agent is built (``add_consumer`` + ``load_tools``)
and closes it on ``agent.cleanup()`` (``remove_consumer``, ref-counted). Loom no
longer starts, lists, or closes MCP connections itself.

Transport callables come from the ``mcp`` package and are resolved through the
ACL's ``resolve`` for version tolerance.
"""

import logging

from loom.adapters import strands as sx
from loom.adapters.strands import resolve
from loom.core.exceptions import AgentConfigError
from loom.schemas.config.mcp import MCPServerConfig, StdioMCPServer

logger = logging.getLogger(__name__)


def _build_transport(server: MCPServerConfig):
    """Return a transport callable (``Callable[[], AsyncContextManager]``) for ``server``."""
    if isinstance(server, StdioMCPServer):
        stdio_client = resolve("mcp.client.stdio.stdio_client")
        stdio_params_cls = resolve(
            "mcp.StdioServerParameters", "mcp.client.stdio.StdioServerParameters"
        )
        params = stdio_params_cls(command=server.command, args=server.args, env=server.env)
        return lambda: stdio_client(params)

    # Remote transports (http | sse) share the url/headers shape.
    factory = resolve(
        "mcp.client.streamable_http.streamablehttp_client"
        if server.transport == "http"
        else "mcp.client.sse.sse_client"
    )
    url, headers = server.url, server.headers
    return lambda: factory(url=url, headers=headers)


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

    clients = [sx.MCPClient(_build_transport(server), prefix=server.name) for server in servers]
    logger.info("Prepared %d MCP client(s) as tool providers", len(clients))
    return clients
