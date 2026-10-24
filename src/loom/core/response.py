"""
loom.core.response — Pure helpers that turn a Strands ``AgentResult`` into Loom's
``AgentResponse`` (and persist per-invocation stats).

These carry no instance state, so they live here as plain functions shared by the
dev-only executor (:func:`loom.dev.run_dev`). They depend only on a
:class:`~loom.schemas.context.LoomSession` for identity — not on any ambient
execution context — so they work the same in dev and when called directly.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from loom.core.paths import build_workspace_paths
from loom.schemas.context import LoomSession
from loom.schemas.response import AgentResponse, AgentResponseMetadata, InterruptInfo

logger = logging.getLogger(__name__)

# Rough chars-per-token heuristic. This is a display-only estimate for the system
# prompt; real token usage is reported by the model in AgentResponseMetadata.
_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Very rough token count (chars / 4) — for display only, not billing-accurate."""
    return len(text) // _CHARS_PER_TOKEN


def extract_interrupts(result: Any) -> list[InterruptInfo]:
    """Map any pending Strands interrupts on the result to ``InterruptInfo``."""
    raw = getattr(result, "interrupts", None) or []
    interrupts: list[InterruptInfo] = []
    for item in raw:
        if isinstance(item, dict):
            interrupts.append(
                InterruptInfo(
                    id=str(item.get("id", "")),
                    name=str(item.get("name", "")),
                    reason=item.get("reason"),
                )
            )
        else:
            interrupts.append(
                InterruptInfo(
                    id=str(getattr(item, "id", "")),
                    name=str(getattr(item, "name", "")),
                    reason=getattr(item, "reason", None),
                )
            )
    return interrupts


def build_metadata(
    result: Any,
    session: LoomSession,
    *,
    model_id: str | None,
    user_msg_idx: int,
    assistant_msg_idx: int,
) -> AgentResponseMetadata:
    """Extract token counts, latency and tool usage from the result into metadata."""
    raw_metrics = result.metrics.get_summary() or {}
    usage = raw_metrics.get("accumulated_usage", {})

    return AgentResponseMetadata(
        session_id=session.session_id,
        user_id=session.user_id,
        user_msg_idx=user_msg_idx,
        assistant_msg_idx=assistant_msg_idx,
        input_tokens=usage.get("inputTokens", 0),
        output_tokens=usage.get("outputTokens", 0),
        total_tokens=usage.get("totalTokens", 0),
        response_time_ms=raw_metrics.get("total_duration", 0.0),
        tool_calls=list[str](raw_metrics.get("tool_usage", {}).keys()),
        model_id=model_id,
        raw_metrics=raw_metrics,
    )


def build_response(
    result: Any,
    session: LoomSession,
    *,
    model_id: str | None,
    user_msg_idx: int,
    assistant_msg_idx: int,
) -> AgentResponse:
    """Assemble an ``AgentResponse`` (answer + metadata + interrupts) from a result."""
    try:
        content = result.message.get("content", [])
        if not content:
            logger.warning("Empty content in agent result message")
            answer = ""
        else:
            answer = content[0].get("text", "")
            if not answer:
                logger.debug("Empty text in first content block, using fallback")
    except (KeyError, IndexError, TypeError) as e:
        logger.error("Failed to extract answer from agent result: %s", str(e), exc_info=True)
        answer = ""

    metadata = build_metadata(
        result,
        session,
        model_id=model_id,
        user_msg_idx=user_msg_idx,
        assistant_msg_idx=assistant_msg_idx,
    )
    return AgentResponse(
        answer=answer,
        metadata=metadata,
        interrupts=extract_interrupts(result),
        checkpoint=_checkpoint(result),
    )


def _checkpoint(result: Any) -> dict | None:
    """Copy a checkpoint when the turn stopped to be resumed."""
    if getattr(result, "stop_reason", None) != "checkpoint":
        return None
    raw = getattr(result, "checkpoint", None)
    if raw is None:
        return None
    if hasattr(raw, "to_dict"):
        data = raw.to_dict()
        return dict(data) if isinstance(data, dict) else None
    if isinstance(raw, dict):
        return dict(raw)
    return None


def run_and_record(
    agent: Any,
    agent_input: Any,
    session: LoomSession,
    *,
    model_id: str | None,
    name: str,
    system_prompt_tokens: int,
    invocation_state: dict[str, Any] | None = None,
) -> tuple[AgentResponse, bool]:
    """Run a built Strands agent once, assemble the response and persist stats.

    The execution core of the dev-only executor (:func:`loom.dev.run_dev`). It
    only runs the agent and records the outcome — it does **not** open or close
    MCP connections, leaving that policy to the caller.

    Args:
        agent: A built ``strands.Agent``.
        agent_input: The normalised input (string query or content blocks).
        session: The identity (``session_id``/``user_id``) for this invocation.
        model_id: Resolved model id, for the response metadata.
        name: Agent name, for the persisted stats record.
        system_prompt_tokens: Estimated system-prompt tokens, for the stats record.
        invocation_state: Free-form context forwarded to Strands as native
            ``invocation_state`` — tools/hooks read it via
            ``tool_context.invocation_state``. Replaces the old ``LoomContext``.

    Returns:
        ``(response, interrupted)`` — the assembled response and whether the
        agent paused on a pending interrupt (so the caller can decide whether to
        keep it alive for ``resume`` or tear it down).
    """
    user_msg_idx = len(agent.messages)
    result = agent(agent_input, invocation_state=invocation_state or {})
    interrupted = bool(getattr(result, "interrupts", None))
    assistant_msg_idx = len(agent.messages) - 1

    trace = getattr(agent, "_loom_routing_trace", None)
    attempts = list(getattr(trace, "attempts", None) or [])
    if attempts:
        answered = next((item for item in reversed(attempts) if item.get("outcome") == "OK"), None)
        if answered and answered.get("model_id"):
            model_id = answered["model_id"]

    response = build_response(
        result,
        session,
        model_id=model_id,
        user_msg_idx=user_msg_idx,
        assistant_msg_idx=assistant_msg_idx,
    )
    if attempts:
        response.metadata.model_attempts = attempts
    save_invocation(response.metadata, name=name, system_prompt_tokens=system_prompt_tokens)
    return response, interrupted


def save_invocation(
    metadata: AgentResponseMetadata, *, name: str, system_prompt_tokens: int
) -> None:
    """Append the invocation record to ``.loom/stats/{name}.jsonl`` (best-effort).

    Persists Strands' own metrics summary verbatim under ``metrics`` plus Loom's
    session context — no re-derived fields. ``loom agent stats`` aggregates from
    the summary.
    """
    try:
        record: dict[str, Any] = {
            "ts": datetime.now(tz=UTC).isoformat(),
            "session_id": metadata.session_id,
            "user_id": metadata.user_id,
            "system_prompt_tokens": system_prompt_tokens,
            "metrics": metadata.raw_metrics or {},
            "model_id": metadata.model_id,
            "model_attempts": metadata.model_attempts,
        }
        stats_file = build_workspace_paths().agent_stats_file(name)
        stats_file.parent.mkdir(parents=True, exist_ok=True)
        with stats_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        logger.debug(
            "Invocation saved to stats: agent=%s tokens=%d latency=%.0fms",
            name,
            metadata.total_tokens,
            metadata.response_time_ms,
        )
    except Exception as e:
        logger.error(
            "Failed to save invocation stats for agent '%s': %s", name, str(e), exc_info=True
        )
