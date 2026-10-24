"""Schema for the global app.yml configuration file."""

from typing import Literal

from loom.config.defaults import DEFAULT_REGION

from .conversations import ConversationConfig
from .sessions import SessionConfig
from .storage import StorageConfig
from .strict import StrictConfig
from .telemetry import TelemetryConfig


class AppConfig(StrictConfig):
    """Global application settings loaded from ``app.yml``."""

    # No persistence by default: a factory should not silently write conversation
    # state to disk. Persistence is opt-in (set ``session:`` in app.yml, or let a
    # harness like Weave own history — two persistences are the poisoned-session
    # bug). ``loom init`` scaffolds an explicit session block for standalone use.
    session: SessionConfig | None = None
    # Shared backend for subsystems that do not declare their own storage.
    storage: StorageConfig | None = None
    # Profile name (resolved from loom.config.profiles) or an inline config.
    conversation: str | ConversationConfig | None = "none"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    region: str = DEFAULT_REGION
    defaults: dict | None = None
    telemetry: TelemetryConfig | None = None
