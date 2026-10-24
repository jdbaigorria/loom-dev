"""MCP transports. The only place Loom touches the ``mcp`` package.

HTTP streamable transport is not built here: on Strands >= 1.53 (and therefore
on the 1.62 floor) ``MCPClient(url=...)`` owns the mcp 1.x/2.x differences.
"""

from loom.adapters.strands import resolve


def stdio_transport(command: str, args: list[str] | None, env: dict[str, str] | None):
    """Transport callable for a local stdio MCP server."""
    stdio_client = resolve("mcp.client.stdio.stdio_client")
    params_cls = resolve("mcp.StdioServerParameters", "mcp.client.stdio.StdioServerParameters")
    params = params_cls(command=command, args=args or [], env=env)
    return lambda: stdio_client(params)


def sse_transport(url: str, headers: dict[str, str] | None):
    """Transport callable for a remote SSE MCP server."""
    sse_client = resolve("mcp.client.sse.sse_client")
    return lambda: sse_client(url=url, headers=headers)
