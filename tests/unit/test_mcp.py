"""Tests for declarative MCP servers (schema, loader, lifecycle).

Real MCP servers are external processes, so the connection itself is not
exercised here; instead the wiring is verified with a mocked MCPClient — that the
loader builds one *unstarted* client per server (namespaced by name) to hand to
the agent as a ToolProvider, and that the dev executor tears them down via
``agent.cleanup()`` afterward.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import TypeAdapter, ValidationError

from loom.core.exceptions import AgentConfigError
from loom.core.loaders.mcp import get_mcp_clients
from loom.schemas.config.mcp import MCPServerConfig, RemoteMCPServer, StdioMCPServer

_adapter: TypeAdapter = TypeAdapter(MCPServerConfig)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class TestMCPSchema:
    def test_stdio_discriminator(self):
        s = _adapter.validate_python(
            {"name": "fs", "transport": "stdio", "command": "npx", "args": ["-y", "server"]}
        )
        assert isinstance(s, StdioMCPServer)
        assert s.command == "npx" and s.args == ["-y", "server"]

    def test_http_discriminator(self):
        s = _adapter.validate_python({"name": "gh", "transport": "http", "url": "https://x/mcp"})
        assert isinstance(s, RemoteMCPServer)

    def test_sse_discriminator(self):
        s = _adapter.validate_python({"name": "gh", "transport": "sse", "url": "https://x/sse"})
        assert isinstance(s, RemoteMCPServer)

    def test_unknown_transport_rejected(self):
        with pytest.raises(ValidationError):
            _adapter.validate_python({"name": "x", "transport": "grpc", "url": "u"})

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            StdioMCPServer(name="x", command="c", bogus=1)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class TestMCPLoader:
    def test_builds_one_unstarted_client_per_server_namespaced(self):
        servers = [
            StdioMCPServer(name="fs", command="npx", args=["server-fs"]),
            RemoteMCPServer(name="gh", transport="http", url="https://x/mcp"),
        ]

        def factory(transport, *, prefix=None, **kwargs):
            client = MagicMock(name=f"MCPClient[{prefix}]")
            client.prefix = prefix
            return client

        with (
            patch("loom.core.loaders.mcp.sx.MCPClient", factory),
            patch("loom.core.loaders.mcp._build_transport", lambda s: lambda: None),
        ):
            clients = get_mcp_clients(servers)

        assert [c.prefix for c in clients] == ["fs", "gh"]
        # Returned unstarted — the agent's tool registry owns start/stop.
        for c in clients:
            c.start.assert_not_called()

    def test_missing_capability_raises_friendly_error(self):
        with patch("loom.core.loaders.mcp.sx.MCPClient", None):
            with pytest.raises(AgentConfigError, match="does not provide MCP support"):
                get_mcp_clients([StdioMCPServer(name="fs", command="npx")])


# ---------------------------------------------------------------------------
# Lifecycle: run_dev tears the agent (and its MCP providers) down via cleanup()
# ---------------------------------------------------------------------------


class TestMCPLifecycle:
    def test_run_dev_calls_agent_cleanup_after_run(self):
        from loom.dev import DevAgent, run_dev
        from loom.schemas.context import LoomSession

        fake_agent = MagicMock()
        fake_agent.messages = []
        fake_agent.return_value = MagicMock(
            message={"content": [{"text": "ok"}]},
            metrics=MagicMock(get_summary=lambda: {}),
            interrupts=[],
        )
        dev = DevAgent(agent=fake_agent, model_id=None, system_prompt_tokens=0, name="a")

        with (
            patch("loom.dev._resolve_kind", return_value="agent"),
            patch("loom.dev.build_dev_agent", return_value=dev),
            patch("loom.core.response.save_invocation"),
        ):
            run_dev("a", "hi", LoomSession(session_id="s", user_id="u"))

        # The agent's tool registry closes any MCP connections on cleanup().
        fake_agent.cleanup.assert_called_once()
