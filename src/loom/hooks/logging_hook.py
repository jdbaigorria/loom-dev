"""Agent invocation lifecycle logging hook.

Logs agent invocation start and completion events with stop reason information.
Provides basic traceability for agent execution without external infrastructure.

Usage in agent YAML:
    hooks:
      - logging
"""

import logging

from loom.adapters.strands import (
    AfterInvocationEvent,
    BeforeInvocationEvent,
    HookProvider,
    HookRegistry,
)

logger = logging.getLogger(__name__)


class LoggingHook(HookProvider):
    """Log agent invocation start and completion events."""

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        """Register invocation lifecycle callbacks.

        Args:
            registry: Strands HookRegistry for registering event callbacks.
        """
        registry.add_callback(BeforeInvocationEvent, self._on_before)
        registry.add_callback(AfterInvocationEvent, self._on_after)

    def _on_before(self, event: BeforeInvocationEvent) -> None:
        """Log start of agent invocation.

        Args:
            event: BeforeInvocationEvent (contains messages and other state).
        """
        logger.info("[LOOM] Agent invocation started")

    def _on_after(self, event: AfterInvocationEvent) -> None:
        """Log completion of agent invocation with stop reason.

        Args:
            event: AfterInvocationEvent with result including stop_reason.
        """
        stop_reason = event.result.stop_reason if event.result else "unknown"
        logger.info("[LOOM] Agent invocation completed (stop_reason=%s)", stop_reason)
