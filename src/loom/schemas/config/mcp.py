"""Schema for declarative MCP (Model Context Protocol) servers.

An agent can declare one or more MCP servers; their tools are connected at build
time and made available to the model alongside the agent's own tools. Two
transports are supported, selected by the ``transport`` discriminator:

- ``stdio`` — launch a local server process (``command`` + ``args``).
- ``http`` / ``sse`` — connect to a remote server at ``url``.

Each server's tools are namespaced by its ``name`` to avoid collisions.

Example (agent YAML)::

    mcp_servers:
      - name: filesystem
        transport: stdio
        command: npx
        args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
      - name: github
        transport: http
        url: https://mcp.example.com/github
        headers: { Authorization: "Bearer ${oc.env:GITHUB_TOKEN}" }
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class StdioMCPServer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    transport: Literal["stdio"] = "stdio"
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] | None = None


class RemoteMCPServer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    transport: Literal["http", "sse"]
    url: str
    headers: dict[str, str] | None = None


MCPServerConfig = Annotated[
    StdioMCPServer | RemoteMCPServer,
    Field(discriminator="transport"),
]
