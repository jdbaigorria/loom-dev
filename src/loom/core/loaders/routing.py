"""Read Strands model-router attempts without touching private types."""

from __future__ import annotations

from typing import Any

from loom.adapters.strands import AfterInvocationEvent, HookProvider, HookRegistry

_ROUTING_PREFIX = "strands:model_routing"


def routing_attempts(invocation_state: object) -> list[dict[str, Any]]:
    """Copy the current router attempts into plain dicts.

    The state object is private. Missing or unexpected shapes return an empty list.
    """
    return [_attempt_record(item) for item in _raw_attempts(invocation_state)]


def _raw_attempts(invocation_state: object) -> list[Any]:
    if not isinstance(invocation_state, dict):
        return []
    for key, value in invocation_state.items():
        if not isinstance(key, str) or not key.startswith(_ROUTING_PREFIX):
            continue
        raw = getattr(value, "attempts", None)
        if raw:
            return list(raw)
    return []


def _attempt_record(attempt: object) -> dict[str, Any]:
    candidate = getattr(attempt, "candidate", None)
    model = getattr(candidate, "model", None)
    error = getattr(attempt, "exception", None)
    model_id = getattr(model, "model_id", None)
    return {
        "candidate": getattr(candidate, "name", None) or "unknown",
        "model_id": model_id if isinstance(model_id, str) else None,
        "outcome": "OK" if error is None else type(error).__name__,
    }


class RoutingTraceHook(HookProvider):
    """Remember which fallback candidate answered, for response metadata and metrics.

    ``answered_model`` is the model object of the candidate that answered (``None`` if
    none did) and ``failed_attempts`` how many tries failed before it — read by
    :func:`loom.metrics.describe_model`. Registered after the user's hooks, so its
    ``AfterInvocationEvent`` callback runs before theirs (``After*`` run in reverse).
    """

    def __init__(self) -> None:
        self.attempts: list[dict[str, Any]] = []
        self.answered_model: Any = None
        self.failed_attempts = 0

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        if AfterInvocationEvent is None:
            return
        registry.add_callback(AfterInvocationEvent, self._record)

    def _record(self, event: Any) -> None:
        raw = _raw_attempts(getattr(event, "invocation_state", None))
        if raw:
            self.attempts = [_attempt_record(item) for item in raw]
            answered = [item for item in raw if getattr(item, "exception", None) is None]
            candidate = getattr(answered[-1], "candidate", None) if answered else None
            self.answered_model = getattr(candidate, "model", None)
            self.failed_attempts = len(raw) - len(answered)
