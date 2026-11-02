"""
loom.hooks.metrics — Per-turn metrics for any agent, handed to a sink.

Marks the trace count on ``BeforeInvocationEvent`` and, on ``AfterInvocationEvent``,
projects the turn with :func:`loom.metrics.turn_metrics_of` and hands it to a sink.
Strands fires ``AfterInvocationEvent`` from a ``finally``, so a failed turn is reported
too (``outcome="error"``, with the tools that ran).

Usage in YAML:
    hooks:
      - metrics                                  # sink: log (default)
      - metrics:
          sink: emf                              # Embedded Metric Format to stdout
          namespace: Acme/Agents
          include: [breakdown, tools]
      - metrics:
          sink: acme_app.metrics:publish         # publish(metrics, context)

Loom does not depend on AWS or Powertools: ``log`` and ``emf`` use the standard library.
Publishing with an SDK is the product's ``module:function`` sink.
"""

import json
import logging
import sys
import time
from collections.abc import Callable, Sequence
from typing import Any, cast

from loom.adapters.strands import (
    AfterInvocationEvent,
    BeforeInvocationEvent,
    HookProvider,
    HookRegistry,
)
from loom.core.exceptions import HookLoadError
from loom.metrics import TurnContext, TurnMetrics, describe_model, turn_metrics_of, variant_of
from loom.schemas.context import LoomSession
from loom.utils.loaders import import_attr

logger = logging.getLogger(__name__)
turn_logger = logging.getLogger("loom.metrics")

Sink = Callable[[TurnMetrics, TurnContext], None]

GROUPS = ("invocation", "breakdown", "tools")
_TRUE = {"true", "1", "yes", "on"}
_FALSE = {"false", "0", "no", "off"}


class MetricsHook(HookProvider):
    """Hand each invocation's :class:`~loom.metrics.TurnMetrics` to a sink.

    Args:
        sink: ``"log"`` (one INFO line on ``loom.metrics``), ``"emf"`` (EMF JSON to
            stdout) or ``"module:function"`` called as ``function(metrics, context)``.
        include: ``emf`` only — groups to emit: ``invocation``, ``breakdown``, ``tools``.
        namespace: ``emf`` only, required — CloudWatch namespace.
        service: ``emf`` only — adds a ``service`` dimension.
        enabled: ``False`` registers no callbacks. Accepts the strings an
            ``${oc.env:...}`` interpolation yields (``"true"``, ``"0"``, ``"off"``…).
    """

    def __init__(
        self,
        sink: str = "log",
        include: Sequence[str] | None = None,
        namespace: str | None = None,
        service: str | None = None,
        enabled: bool | str = True,
    ) -> None:
        self._enabled = _as_bool(enabled)
        self._send = _resolve_sink(sink, include=include, namespace=namespace, service=service)
        self._since: int | None = None
        self._agent: str | None = None
        self._session: LoomSession | None = None

    def loom_bind(self, *, agent: str, session: LoomSession) -> None:
        """Receive the agent name and session from the builder (``SessionAwareHook``)."""
        self._agent = agent
        self._session = session

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        if not self._enabled:
            return
        registry.add_callback(BeforeInvocationEvent, self._mark)
        registry.add_callback(AfterInvocationEvent, self._emit)

    def _mark(self, event: Any) -> None:
        try:
            self._since = len(event.agent.event_loop_metrics.traces)
        except Exception:
            self._since = None
            logger.warning("[LOOM] metrics hook could not mark the turn start", exc_info=True)

    def _emit(self, event: Any) -> None:
        # Strands propagates exceptions from After* callbacks: nothing here may break the turn.
        try:
            metrics = turn_metrics_of(event.agent, since_trace=self._since or 0)
            result = event.result
            stop_reason = getattr(result, "stop_reason", None) if result is not None else None
            model = describe_model(event.agent)
            context = TurnContext(
                agent=self._agent or str(getattr(event.agent, "name", "") or "unknown"),
                session_id=self._session.session_id if self._session else None,
                user_id=self._session.user_id if self._session else None,
                outcome="ok" if result is not None else "error",
                stop_reason=str(stop_reason) if stop_reason is not None else None,
                model_id=model.model_id,
                model_settings=model.settings,
                model_fallbacks=model.fallbacks,
                variant=variant_of(event.agent),
            )
            self._send(metrics, context)
        except Exception:
            logger.warning("[LOOM] metrics hook failed", exc_info=True)
        finally:
            self._since = None


def _resolve_sink(
    sink: str, *, include: Sequence[str] | None, namespace: str | None, service: str | None
) -> Sink:
    if sink == "emf":
        if not isinstance(namespace, str) or not namespace:
            raise HookLoadError(
                "The metrics hook with sink: emf needs a namespace.",
                tip="Add 'namespace: <CloudWatch namespace>' to the metrics hook params.",
            )
        groups = tuple(GROUPS if include is None else include)
        unknown = [g for g in groups if g not in GROUPS]
        if unknown or not groups:
            raise HookLoadError(
                f"Invalid metrics include: {list(groups)}.",
                tip=f"Use one or more of {list(GROUPS)}.",
            )
        return EmfSink(namespace, service=service, include=groups)

    extra = [
        n
        for n, v in (("namespace", namespace), ("service", service), ("include", include))
        if v is not None
    ]
    if extra:
        raise HookLoadError(
            f"Metrics hook params {extra} only apply to sink: emf.",
            tip="Remove them, or set 'sink: emf'.",
        )
    if sink == "log":
        return log_sink
    if ":" not in sink and "." not in sink:
        raise HookLoadError(
            f"Unknown metrics sink '{sink}'.",
            tip="Use 'log', 'emf' or an importable 'module:function'.",
        )
    try:
        target = import_attr(sink)
    except (ImportError, AttributeError, ValueError) as e:
        raise HookLoadError(
            f"Metrics sink '{sink}' could not be imported.",
            tip=f"Verify the module is installed and defines the function. Error: {e}",
        ) from e
    if not callable(target):
        raise HookLoadError(
            f"Metrics sink '{sink}' is not callable.",
            tip="Point it at a function taking (metrics, context).",
        )
    return cast(Sink, target)


def log_sink(metrics: TurnMetrics, context: TurnContext) -> None:
    """One INFO line per turn on ``loom.metrics``, with the full data in ``extra``."""
    if not turn_logger.isEnabledFor(logging.INFO):
        return
    turn_logger.info(
        "turn agent=%s model=%s outcome=%s duration_ms=%d model_ms=%d tools_ms=%d cycles=%d tokens=%d",
        context.agent,
        context.model_id,
        context.outcome,
        metrics.duration_ms,
        metrics.model_ms,
        metrics.tools_ms,
        len(metrics.cycles),
        metrics.usage.get("totalTokens", 0),
        extra={"turn": metrics.model_dump(mode="json"), "context": context.model_dump()},
    )


class EmfSink:
    """CloudWatch Embedded Metric Format, one JSON line per group, straight to stdout.

    Not through ``logging``: EMF needs the JSON to be the whole line, and a logging
    handler (Lambda's, Powertools') would prefix or wrap it.
    """

    def __init__(self, namespace: str, *, service: str | None, include: Sequence[str]) -> None:
        self.namespace = namespace
        self.service = service
        self.include = tuple(include)

    def __call__(self, metrics: TurnMetrics, context: TurnContext) -> None:
        properties: dict[str, Any] = {
            k: v
            for k, v in (
                ("session_id", context.session_id),
                ("user_id", context.user_id),
                ("outcome", context.outcome),
                ("stop_reason", context.stop_reason),
                ("model", context.model_id),
                ("variant", context.variant),
            )
            if v is not None
        }
        if context.model_settings is not None:
            properties["model_config"] = context.model_settings.model_dump(exclude_none=True)
        properties["model_fallbacks"] = context.model_fallbacks
        turn: list[tuple[str, str, float]] = []
        if "invocation" in self.include:
            turn += [
                ("Invocations", "Count", 1),
                ("InvocationErrors", "Count", 0 if context.outcome == "ok" else 1),
                ("InvocationDuration", "Milliseconds", metrics.duration_ms),
            ]
            if context.outcome == "ok":
                for name, key in (
                    ("InputTokens", "inputTokens"),
                    ("OutputTokens", "outputTokens"),
                    ("TotalTokens", "totalTokens"),
                ):
                    if key in metrics.usage:
                        turn.append((name, "Count", metrics.usage[key]))
        if "breakdown" in self.include:
            turn += [
                ("ModelDuration", "Milliseconds", metrics.model_ms),
                ("ToolsDuration", "Milliseconds", metrics.tools_ms),
                ("OtherDuration", "Milliseconds", metrics.other_ms),
                ("Cycles", "Count", len(metrics.cycles)),
            ]
        if turn:
            # One line, several aggregations: per agent (as before), per agent and model, and
            # per agent and variant. Each extra set is one more series per metric.
            sets = [self._dimensions(agent=context.agent)]
            if context.model_id:
                sets.append(self._dimensions(agent=context.agent, model=context.model_id))
            if context.variant:
                sets.append(self._dimensions(agent=context.agent, variant=context.variant))
            self._write(sets, turn, properties)
        if "tools" in self.include:
            for cycle in metrics.cycles:
                for call in cycle.tools:
                    self._write(
                        [self._dimensions(agent=context.agent, tool=call.name)],
                        [
                            ("ToolDuration", "Milliseconds", call.elapsed_ms),
                            ("ToolInvocations", "Count", 1),
                            ("ToolErrors", "Count", 1 if call.status == "error" else 0),
                        ],
                        {**properties, "tool_use_id": call.tool_use_id},
                    )

    def _dimensions(self, **values: str) -> dict[str, str]:
        return {**values, **({"service": self.service} if self.service else {})}

    def _write(
        self,
        dimension_sets: list[dict[str, str]],
        values: list[tuple[str, str, float]],
        properties: dict[str, Any],
    ) -> None:
        # EMF needs every dimension's value at the root, once.
        dimensions = {k: v for dims in dimension_sets for k, v in dims.items()}
        doc = {
            "_aws": {
                "Timestamp": int(time.time() * 1000),
                "CloudWatchMetrics": [
                    {
                        "Namespace": self.namespace,
                        "Dimensions": [list(dims) for dims in dimension_sets],
                        "Metrics": [{"Name": name, "Unit": unit} for name, unit, _ in values],
                    }
                ],
            },
            **properties,
            **dimensions,
            **{name: value for name, _, value in values},
        }
        print(json.dumps(doc), file=sys.stdout, flush=True)


def _as_bool(value: bool | str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in _TRUE | _FALSE:
        return value.strip().lower() in _TRUE
    raise HookLoadError(
        f"Metrics hook 'enabled' must be a boolean, got {value!r}.",
        tip="Use true/false, or an ${oc.env:...} interpolation that yields one.",
    )
