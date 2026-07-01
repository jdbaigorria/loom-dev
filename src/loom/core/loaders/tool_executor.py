"""
loom.core.loaders.tool_executor — Build the agent's tool execution strategy.

Maps the declarative ``tool_executor`` value (``concurrent`` | ``sequential``)
to a Strands ``ToolExecutor`` instance. Pluggable tool executors are a newer
Strands capability; if the installed version lacks them, a clear ``AgentConfigError``
is raised instead of a cryptic import failure.
"""

import logging
from typing import Literal

from loom.adapters import strands as sx
from loom.core.exceptions import AgentConfigError

logger = logging.getLogger(__name__)


def get_tool_executor(strategy: Literal["concurrent", "sequential"]):
    """Instantiate the configured tool executor.

    Args:
        strategy: ``"concurrent"`` or ``"sequential"``.

    Returns:
        A Strands ``ToolExecutor`` instance.

    Raises:
        AgentConfigError: If the installed Strands version has no pluggable tool
            executors, or the strategy is unknown.
    """
    # Capability check first: distinguish "Strands too old" from "bad strategy".
    if sx.ConcurrentToolExecutor is None or sx.SequentialToolExecutor is None:
        raise AgentConfigError(
            "The installed Strands version does not provide pluggable tool executors.",
            tip="Upgrade strands-agents to a version that ships strands.tools.executors, "
            "or remove 'tool_executor' from the agent YAML.",
        )

    registry = {
        "concurrent": sx.ConcurrentToolExecutor,
        "sequential": sx.SequentialToolExecutor,
    }
    cls = registry.get(strategy)
    if cls is None:
        raise AgentConfigError(
            f"Invalid tool_executor: {strategy}",
            tip=f"Use one of: {list(registry)}",
        )

    logger.debug("Tool executor: strategy=%s", strategy)
    return cls()
