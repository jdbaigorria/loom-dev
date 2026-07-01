"""
loom.hooks.tool_tracker — Logs each tool call with its name and result.

Records in the logger when a tool is invoked, its name, and whether it
completed or failed. Useful for debugging and auditing tool-heavy flows.

Usage in YAML:
    hooks:
      - tool_tracker
"""

import logging

from loom.adapters.strands import (
    AfterToolCallEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)

logger = logging.getLogger(__name__)


class ToolTrackerHook(HookProvider):
    """Log and track each tool call with input parameters and output summary."""

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        """Register hook callbacks for tool execution events.

        Args:
            registry: Strands HookRegistry for registering event callbacks.
        """
        registry.add_callback(BeforeToolCallEvent, self._on_before_tool)
        registry.add_callback(AfterToolCallEvent, self._on_after_tool)

    def _on_before_tool(self, event: BeforeToolCallEvent) -> None:
        """Log tool invocation with parameters before execution.

        Args:
            event: BeforeToolCallEvent with tool name and input data.
        """
        name = event.tool_use["name"]
        input_data = event.tool_use.get("input", {})
        param_names = list(input_data.keys()) if isinstance(input_data, dict) else []
        logger.info("[LOOM] Tool call: %s (params=%s)", name, param_names)
        logger.debug("[LOOM] Tool input for '%s': %s", name, input_data)

    def _on_after_tool(self, event: AfterToolCallEvent) -> None:
        """Log tool completion with response metadata or error information.

        Args:
            event: AfterToolCallEvent with tool result or exception information.
        """
        name = event.tool_use["name"]
        if event.exception:
            logger.error("[LOOM] Tool '%s' failed: %s", name, event.exception, exc_info=True)
        else:
            result = getattr(event, "tool_result", None) or {}
            result_size = len(str(result)) if result else 0
            result_type = type(result).__name__
            logger.debug(
                "[LOOM] Tool '%s' completed: response_type=%s, size=%d bytes",
                name,
                result_type,
                result_size,
            )
            if result:
                logger.debug("[LOOM] Tool result for '%s': %s", name, str(result)[:200])
