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


class ModelSettings(_Frozen):
    """The model configuration that is safe and useful to publish — a whitelist.

    Names are normalized across providers (``effort`` is Bedrock's
    ``output_config.effort``, OpenAI's ``reasoning_effort`` and Nova's
    ``maxReasoningEffort``). ``None`` means "not set": the provider default applies.
    Anything not listed here (credentials, ``stop_sequences``, guardrail ids, any other
    ``params`` or ``additional_request_fields``) is never read.
    """

    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    streaming: bool | None = None
    effort: str | None = None
    thinking: str | None = None
    thinking_budget: int | None = None
    service_tier: str | None = None
    prompt_cache: bool | None = None
    guardrail: bool | None = None


class ModelDescription(_Frozen):
    """Which model answered and with which settings. ``fallbacks``: failed router attempts."""

    model_id: str | None = None
    settings: ModelSettings = ModelSettings()
    fallbacks: int = 0


class TurnContext(_Frozen):
    """What a metrics sink needs besides the numbers. No content, no ``invocation_state``.

    ``outcome`` is ``"error"`` when the invocation produced no ``AgentResult``.
    """

    agent: str
    session_id: str | None = None
    user_id: str | None = None
    outcome: Literal["ok", "error"]
    stop_reason: str | None = None
    model_id: str | None = None
    model_settings: ModelSettings | None = None
    model_fallbacks: int = 0
    variant: str | None = None


VARIANT_LABEL = "metrics.variant"


def describe_model(agent: Any) -> ModelDescription:
    """The model that answered the agent's last turn, with its whitelisted settings.

    With a model router (fallback / route) it is the candidate that answered, read from
    Loom's routing trace, with that candidate's own settings. Never raises: anything
    unexpected gives an empty ``ModelDescription``.
    """
    try:
        model = getattr(agent, "model", None)
        fallbacks = 0
        trace = getattr(agent, "_loom_routing_trace", None)
        if trace is not None:
            answered = getattr(trace, "answered_model", None)
            if answered is not None:
                model = answered
            fallbacks = _int(getattr(trace, "failed_attempts", 0)) or 0
        if model is None:
            return ModelDescription()
        # A nested router contributes one candidate: describe its default model.
        model = getattr(model, "default_model", None) or model
        config = _config_of(model)
        model_id = _str(config.get("model_id")) or _str(getattr(model, "model_id", None))
        return ModelDescription(
            model_id=model_id, settings=_settings(config, agent), fallbacks=fallbacks
        )
    except Exception:
        return ModelDescription()


def variant_of(agent: Any) -> str | None:
    """The agent's ``metrics.variant`` label, for comparing two configurations of a model.

    Only scalars count (``True`` → ``"true"``); a list gives ``None``.
    """
    labels = getattr(agent, "_loom_labels", None)
    value = labels.get(VARIANT_LABEL) if isinstance(labels, dict) else None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value)
    return None


def _config_of(model: Any) -> dict[str, Any]:
    get_config = getattr(model, "get_config", None)
    config = get_config() if callable(get_config) else getattr(model, "config", None)
    return config if isinstance(config, dict) else {}


def _settings(config: dict[str, Any], agent: Any) -> ModelSettings:
    params = _dict(config.get("params"))
    extra = _dict(config.get("additional_request_fields"))
    output_config = _dict(extra.get("output_config"))
    thinking = _dict(extra.get("thinking"))
    reasoning = _dict(extra.get("reasoningConfig"))
    return ModelSettings(
        max_tokens=_first(
            _int,
            config.get("max_tokens"),
            params.get("max_tokens"),
            params.get("max_completion_tokens"),
        ),
        temperature=_first(_float, config.get("temperature"), params.get("temperature")),
        top_p=_first(_float, config.get("top_p"), params.get("top_p")),
        top_k=_first(_int, extra.get("top_k"), params.get("top_k")),
        streaming=_first(
            _bool, config.get("streaming"), config.get("stream"), params.get("stream")
        ),
        effort=_first(
            _str,
            output_config.get("effort"),
            params.get("reasoning_effort"),
            reasoning.get("maxReasoningEffort"),
        ),
        thinking=_first(_str, thinking.get("type"), reasoning.get("type")),
        thinking_budget=_first(_int, thinking.get("budget_tokens")),
        service_tier=_first(_str, config.get("service_tier"), params.get("service_tier")),
        prompt_cache=bool(
            config.get("cache_config")
            or config.get("cache_prompt")
            or _has_cache_point(getattr(agent, "system_prompt_content", None))
        ),
        guardrail=bool(config.get("guardrail_id")),
    )


def _has_cache_point(blocks: Any) -> bool:
    return isinstance(blocks, list) and any(
        isinstance(block, dict) and "cachePoint" in block for block in blocks
    )


def _first(convert: Any, *values: Any) -> Any:
    for value in values:
        converted = convert(value)
        if converted is not None:
            return converted
    return None


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


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
