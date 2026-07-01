"""loom.adapters.strands.capabilities — Feature detection for the installed Strands.

Lets Loom expose newer Strands features (tool executors, plugins, A2A, interrupts)
only when the installed version actually provides them, degrading gracefully with
a clear warning instead of crashing with an ``ImportError`` on older versions.

Usage::

    from loom.adapters.strands import capabilities

    if capabilities.has_tool_executor():
        ...  # wire the declarative tool_executor config

Each check is a cheap ``is_available`` probe against candidate import paths.
"""

from __future__ import annotations

from functools import cache

from ._resolve import is_available


@cache
def has_tool_executor() -> bool:
    """True if Strands exposes pluggable tool executors (concurrent/sequential)."""
    return is_available(
        "strands.tools.executors.ConcurrentToolExecutor",
        "strands.tools.executor.ConcurrentToolExecutor",
    )


@cache
def has_plugins() -> bool:
    """True if Strands exposes the Plugin system."""
    return is_available(
        "strands.plugins.Plugin",
        "strands.agent.plugins.Plugin",
    )


@cache
def has_a2a() -> bool:
    """True if Strands exposes the Agent-to-Agent (A2A) protocol."""
    return is_available(
        "strands.multiagent.a2a.A2AServer",
        "strands.a2a.A2AServer",
    )


@cache
def has_swarm() -> bool:
    """True if Strands exposes the Swarm multi-agent primitive."""
    return is_available(
        "strands.multiagent.Swarm",
        "strands.multiagent.swarm.Swarm",
    )


@cache
def has_graph() -> bool:
    """True if Strands exposes the GraphBuilder multi-agent primitive."""
    return is_available(
        "strands.multiagent.GraphBuilder",
        "strands.multiagent.graph.GraphBuilder",
    )


@cache
def has_interrupts() -> bool:
    """True if Strands exposes interrupt / human-in-the-loop handling."""
    return is_available(
        "strands.types.interrupt.Interrupt",
        "strands.interrupt.Interrupt",
    )


@cache
def has_telemetry() -> bool:
    """True if Strands exposes the OpenTelemetry setup helper."""
    return is_available(
        "strands.telemetry.StrandsTelemetry",
        "strands.telemetry.config.StrandsTelemetry",
    )


@cache
def has_mcp() -> bool:
    """True if Strands exposes the MCP (Model Context Protocol) client."""
    return is_available(
        "strands.tools.mcp.MCPClient",
        "strands.tools.mcp.mcp_client.MCPClient",
    )


@cache
def has_bidi() -> bool:
    """True if Strands exposes the experimental bidirectional (full-duplex) agent."""
    return is_available(
        "strands.experimental.bidi.BidiAgent",
        "strands.experimental.bidi.agent.BidiAgent",
    )


def snapshot() -> dict[str, bool]:
    """Return a dict of all capability flags (handy for ``loom doctor``/logging)."""
    return {
        "tool_executor": has_tool_executor(),
        "plugins": has_plugins(),
        "a2a": has_a2a(),
        "swarm": has_swarm(),
        "graph": has_graph(),
        "interrupts": has_interrupts(),
        "telemetry": has_telemetry(),
        "mcp": has_mcp(),
        "bidi": has_bidi(),
    }
