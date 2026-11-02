"""
loom.metrics — Typed per-turn projection of Strands' metrics summary.

Strands hands back ``result.metrics.get_summary()`` raw: traces nested by cycle, tool
stats, token usage. Reading *how long the model took, how long each tool took and in
which cycle* means walking that structure, and every product ended up writing the same
walker. :func:`turn_metrics` is that walker, once, returning a frozen
:class:`TurnMetrics`.

Reading rules (Strands 1.62):

- Each ``Cycle N`` trace ends **before** the recursive call into the next cycle, so
  summing cycles does not count the next answer twice. The ``Recursive call`` child is
  skipped: its time is in the cycle below.
- A trace's ``duration`` is in seconds; the provider's ``latencyMs`` and
  ``timeToFirstByteMs`` on the model message are already milliseconds.
- ``EventLoopMetrics`` accumulates every turn the ``Agent`` instance ran. An agent built
  for one turn needs ``since_trace=0``; a reused agent passes the trace count taken
  before invoking.

Pure functions over plain dicts: no Powertools, no AWS, and **never** message text or
tool arguments — a ``TurnMetrics`` is safe to log and to return to a client.
"""

from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

_RECURSIVE_CALL = "Recursive call"
_MODEL_TRACE = "stream_messages"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class ModelCall(_Frozen):
    """One model call. ``total_ms`` is the ``stream_messages`` wall clock, not the provider's."""

    total_ms: int
    latency_ms: int | None = None
    first_token_ms: int | None = None


class ToolCall(_Frozen):
    """One tool call. ``status`` is ``None`` when the call produced no result (interrupt)."""

    tool_use_id: str
    name: str
    elapsed_ms: int
    status: Literal["success", "error"] | None = None


class Cycle(_Frozen):
    """One event-loop cycle: the model call and the tools it asked for.

    ``complete`` is ``False`` when the cycle never ended (the turn failed inside it);
    ``total_ms`` is then the sum of its finished children.
    """

    total_ms: int
    model: ModelCall | None = None
    tools: tuple[ToolCall, ...] = ()
    complete: bool = True


class TurnMetrics(_Frozen):
    """What one turn cost, split by model, tools and the rest."""

    duration_ms: int = 0
    model_ms: int = 0
    tools_ms: int = 0
    other_ms: int = 0
    cycles: tuple[Cycle, ...] = ()
    usage: dict[str, int] = {}
    tool_errors: dict[str, int] = {}


def turn_metrics(summary: dict[str, Any], *, since_trace: int = 0) -> TurnMetrics:
    """Project a Strands ``get_summary()`` onto one turn.

    Args:
        summary: ``EventLoopMetrics.get_summary()`` (or an equivalent dict).
        since_trace: Index of the turn's first trace. ``0`` when the agent was built for
            this turn; ``len(agent.event_loop_metrics.traces)`` taken before invoking when
            the agent is reused.

    Returns:
        The turn's metrics. Traces without the expected fields are skipped, never raised
        on; an empty summary gives a zeroed ``TurnMetrics``.
    """
    traces = summary.get("traces") if isinstance(summary, dict) else None
    if not isinstance(traces, list):
        traces = []
    cycles = tuple(c for c in (_cycle(node) for node in traces[since_trace:]) if c is not None)

    duration = sum(c.total_ms for c in cycles)
    model = sum(c.model.total_ms for c in cycles if c.model is not None)
    tools = sum(t.elapsed_ms for c in cycles for t in c.tools)
    errors = Counter(t.name for c in cycles for t in c.tools if t.status == "error")
    return TurnMetrics(
        duration_ms=duration,
        model_ms=model,
        tools_ms=tools,
        other_ms=max(0, duration - model - tools),
        cycles=cycles,
        usage=_usage(summary),
        tool_errors=dict(errors),
    )


def turn_metrics_of(agent: Any, *, since_trace: int = 0) -> TurnMetrics:
    """:func:`turn_metrics` over a built ``strands.Agent``'s ``event_loop_metrics``."""
    return turn_metrics(agent.event_loop_metrics.get_summary() or {}, since_trace=since_trace)


def _cycle(node: Any) -> Cycle | None:
    if not isinstance(node, dict):
        return None
    model: ModelCall | None = None
    tools: list[ToolCall] = []
    finished_children = 0
    children = node.get("children")
    for child in children if isinstance(children, list) else []:
        if not isinstance(child, dict) or child.get("name") == _RECURSIVE_CALL:
            continue
        elapsed = _ms(child.get("duration"))
        if elapsed is None:
            continue
        finished_children += elapsed
        raw_metadata = child.get("metadata")
        metadata: dict[str, Any] = raw_metadata if isinstance(raw_metadata, dict) else {}
        name = metadata.get("tool_name")
        if isinstance(name, str) and name:
            tools.append(
                ToolCall(
                    tool_use_id=str(metadata.get("toolUseId") or ""),
                    name=name,
                    elapsed_ms=elapsed,
                    status=_tool_status(child.get("message")),
                )
            )
        elif child.get("name") == _MODEL_TRACE and model is None:
            latency, first_token = _provider_timings(child.get("message"))
            model = ModelCall(total_ms=elapsed, latency_ms=latency, first_token_ms=first_token)

    total = _ms(node.get("duration"))
    if total is None:
        return Cycle(total_ms=finished_children, model=model, tools=tuple(tools), complete=False)
    return Cycle(total_ms=total, model=model, tools=tuple(tools))


def _tool_status(message: Any) -> Literal["success", "error"] | None:
    if not isinstance(message, dict) or not isinstance(message.get("content"), list):
        return None
    for block in message["content"]:
        result = block.get("toolResult") if isinstance(block, dict) else None
        status = result.get("status") if isinstance(result, dict) else None
        if status == "success":
            return "success"
        if status == "error":
            return "error"
    return None


def _provider_timings(message: Any) -> tuple[int | None, int | None]:
    metadata = message.get("metadata") if isinstance(message, dict) else None
    metrics = metadata.get("metrics") if isinstance(metadata, dict) else None
    if not isinstance(metrics, dict):
        return None, None
    return _int_ms(metrics.get("latencyMs")), _int_ms(metrics.get("timeToFirstByteMs"))


def _usage(summary: Any) -> dict[str, int]:
    invocations = summary.get("agent_invocations") if isinstance(summary, dict) else None
    if (
        not isinstance(invocations, list)
        or not invocations
        or not isinstance(invocations[-1], dict)
    ):
        return {}
    usage = invocations[-1].get("usage")
    if not isinstance(usage, dict):
        return {}
    return {k: v for k, v in usage.items() if isinstance(v, int) and not isinstance(v, bool)}


def _ms(seconds: Any) -> int | None:
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        return None
    return max(0, int(round(seconds * 1000)))


def _int_ms(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(0, int(round(value)))
