"""Schema for OpenTelemetry configuration declared in ``app.yml``.

Strands already emits OpenTelemetry traces and metrics for agent invocations,
model calls and tool executions. This config wires up an exporter so that signal
reaches a collector (OTLP — Langfuse, Jaeger, Honeycomb, …) or the console, with
no code from the user. The OTLP endpoint and headers are read from the standard
``OTEL_EXPORTER_OTLP_*`` environment variables.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class TelemetryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    exporter: Literal["otlp", "console"] = "otlp"
    metrics: bool = False
    service_name: str | None = None
    trace_attributes: dict[str, str] | None = None
    baggage_attributes: dict[str, str] | None = None
