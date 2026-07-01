"""
loom.hooks.rate_limit — Limits the number of tool calls per invocation.

Automatically cancels any tool call that exceeds the configured limit.
The counter resets at the start of each new agent invocation.

Usage in YAML:
    hooks:
      - rate_limit:
          max_calls: 10
"""

import logging

from loom.adapters.strands import (
    BeforeInvocationEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)

logger = logging.getLogger(__name__)


class RateLimitHook(HookProvider):
    """Cancel tool calls once the per-invocation limit is exceeded.

    Args:
        max_calls: Maximum number of tool calls allowed per invocation.
            Default: 20.
    """

    def __init__(self, max_calls: int = 20) -> None:
        self._max_calls = max_calls
        self._calls = 0

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        """Register callbacks for invocation start and tool-call events.

        Args:
            registry: Strands HookRegistry for registering event callbacks.
        """
        registry.add_callback(BeforeInvocationEvent, self._reset)
        registry.add_callback(BeforeToolCallEvent, self._check)

    def _reset(self, event: BeforeInvocationEvent) -> None:
        """Reset the call counter at the start of a new invocation.

        Args:
            event: BeforeInvocationEvent signalling a new agent invocation.
        """
        self._calls = 0
        logger.debug("[LOOM] RateLimitHook reset (max_calls=%d)", self._max_calls)

    def _check(self, event: BeforeToolCallEvent) -> None:
        """Increment the counter and cancel the call if the limit is exceeded.

        Args:
            event: BeforeToolCallEvent for the pending tool call.
        """
        self._calls += 1
        if self._calls > self._max_calls:
            msg = (
                f"Rate limit exceeded: max {self._max_calls} tool calls per invocation "
                f"(attempted call #{self._calls})"
            )
            logger.warning("[LOOM] %s", msg)
            event.cancel_tool = msg
