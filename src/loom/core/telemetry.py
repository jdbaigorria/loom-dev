"""
loom.core.telemetry — One-shot OpenTelemetry wiring from ``app.yml``.

Strands instruments agents, model calls and tools with OpenTelemetry out of the
box. :func:`setup_telemetry` reads the declarative ``telemetry`` block from
``app.yml`` and installs an exporter (OTLP or console) once per process, so the
signal Strands already emits actually leaves the process — no user code required.

The OTLP endpoint, headers and protocol come from the standard
``OTEL_EXPORTER_OTLP_*`` environment variables.
"""

import logging
import os

from loom.adapters import strands as sx
from loom.schemas.config.telemetry import TelemetryConfig

logger = logging.getLogger(__name__)

# Process-global guard: OpenTelemetry providers are global and must be set up once.
_initialized = False


def agent_telemetry_attributes(
    config: TelemetryConfig | None, *, session_id: str, user_id: str
) -> tuple[dict[str, str] | None, dict[str, str] | None]:
    """Merge ``session.id`` and ``user.id`` into attributes the user declared.

    Keys the user wrote win. When neither map is declared, both results are
    ``None`` and nothing is passed to the agent.
    """
    if config is None:
        return None, None
    identity = {"session.id": session_id, "user.id": user_id}
    trace = {**identity, **config.trace_attributes} if config.trace_attributes is not None else None
    baggage = (
        {**identity, **config.baggage_attributes} if config.baggage_attributes is not None else None
    )
    return trace, baggage


def setup_telemetry(config: TelemetryConfig | None) -> bool:
    """Initialize OpenTelemetry exporters from the app telemetry config.

    Idempotent: the first enabled call installs the exporter; later calls are
    no-ops. Safe to call on every ``build_agent``.

    Args:
        config: The ``telemetry`` block from ``app.yml`` (or ``None``).

    Returns:
        ``True`` if telemetry is active (now or from a previous call), else
        ``False`` (disabled, unconfigured, or unsupported by this Strands build).
    """
    global _initialized

    if config is None or not config.enabled:
        return False

    if _initialized:
        return True

    if sx.StrandsTelemetry is None:
        logger.warning(
            "Telemetry is enabled in app.yml but this Strands build has no telemetry "
            "support; skipping. Upgrade strands-agents to enable it."
        )
        return False

    # Service name feeds the OTEL Resource; set it before the provider is built.
    if config.service_name:
        os.environ.setdefault("OTEL_SERVICE_NAME", config.service_name)

    telemetry = sx.StrandsTelemetry()
    if config.exporter == "otlp":
        telemetry.setup_otlp_exporter()
    else:
        telemetry.setup_console_exporter()

    if config.metrics:
        telemetry.setup_meter(
            enable_otlp_exporter=config.exporter == "otlp",
            enable_console_exporter=config.exporter == "console",
        )

    _initialized = True
    logger.info("Telemetry initialized (exporter=%s, metrics=%s)", config.exporter, config.metrics)
    return True
