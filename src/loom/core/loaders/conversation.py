"""
loom.core.loaders.conversation — Build the agent's conversation manager.

Supports three conversation history management strategies:

- ``null``: no history (each invocation is independent).
- ``sliding_window``: retains the last N messages.
- ``summarizing``: summarizes history when it exceeds the limit using a
  dedicated Bedrock agent.

The strategy is selected via ``app.yml → conversation.strategy``.
"""

import logging
from collections.abc import Callable
from typing import Any

from loom.adapters import strands as sx
from loom.adapters.strands import (
    Agent,
    BedrockModel,
    ConversationManager,
    NullConversationManager,
    SlidingWindowConversationManager,
    SummarizingConversationManager,
)
from loom.config.profiles import get_profiles
from loom.core.exceptions import AgentConfigError
from loom.schemas.config.conversations import (
    ConversationConfig,
    CustomStrategy,
    SlidingWindowConfig,
    SummarizationAgentConfig,
    SummarizingConfig,
)

logger = logging.getLogger(__name__)


def resolve_conversation_config(conversation: str | ConversationConfig) -> ConversationConfig:
    """Return the concrete ``ConversationConfig`` for a profile name or inline config.

    Raises:
        AgentConfigError: If a profile name is not defined.
    """
    if isinstance(conversation, str):
        profiles = get_profiles()
        cfg = profiles.conversation.get(conversation)
        if cfg is None:
            raise AgentConfigError(
                f"Unknown conversation profile: '{conversation}'",
                tip=f"Use one of {list(profiles.conversation)} or define it in warp/config/profiles.toml.",
            )
        return cfg
    return conversation


def _create_summarizing_agent(config: SummarizationAgentConfig) -> Agent:
    """Create the internal Bedrock agent used to summarize conversation history.

    When no model id is set, defaults to the ``economic`` model profile rather than
    a hardcoded string.
    """
    params = config.model_dump()
    if not params.get("model_id"):
        profile = get_profiles().model["economic"]
        model_id = getattr(profile, "model_id", None)
        if not isinstance(model_id, str):
            raise AgentConfigError("The economic profile must name a single model_id.")
        params["model_id"] = model_id
    model = BedrockModel(**params)
    return Agent(model=model)


def _build_null_manager(config: Any | None = None) -> ConversationManager:
    """Return a ``NullConversationManager`` (no history)."""
    return NullConversationManager()


def _build_sliding_windows_manager(config: SlidingWindowConfig) -> ConversationManager:
    """Build a ``SlidingWindowConversationManager`` with the given configuration."""
    return SlidingWindowConversationManager(**config.model_dump())


def _build_summarizing_manager(config: SummarizingConfig) -> ConversationManager:
    """Build a ``SummarizingConversationManager`` with a summarization agent."""
    params = config.model_dump(exclude={"summarization_agent"})
    if config.summarization_agent is not None:
        agent = _create_summarizing_agent(config.summarization_agent)
        params.update({"summarization_agent": agent})
    return SummarizingConversationManager(**params)


def _build_custom_manager(config: CustomStrategy) -> ConversationManager:
    """Resolve a user-provided ``ConversationManager`` subclass and instantiate it.

    The class is imported through the ACL by dotted ``import_path`` and built with
    the free-form ``config`` params. Loom validates nothing inside ``config``.

    Raises:
        AgentConfigError: If ``import_path`` cannot be resolved.
    """
    cls = sx.resolve(config.import_path, optional=True)
    if cls is None:
        raise AgentConfigError(
            f"Could not import conversation manager class '{config.import_path}'.",
            tip="Check the dotted path and that the package is installed. "
            "Example: my.pkg:MyConversationManager.",
        )
    return cls(**config.config)


CONVERSATION_MANAGER_REGISTRY: dict[str, Callable[[Any], ConversationManager]] = {
    "null": _build_null_manager,
    "sliding_window": _build_sliding_windows_manager,
    "summarizing": _build_summarizing_manager,
}


def get_conversation_manager(
    conversation: str | ConversationConfig,
) -> ConversationManager:
    """Instantiate the conversation manager (profile name or inline config).

    Args:
        conversation: A conversation profile name or an inline ``ConversationConfig``.

    Returns:
        Strands ``ConversationManager`` ready for use with the agent.

    Raises:
        AgentConfigError: If the profile is unknown, the ``strategy`` is invalid,
            or a ``custom`` ``import_path`` cannot be resolved.
    """
    conversation_config = resolve_conversation_config(conversation)

    if isinstance(conversation_config, CustomStrategy):
        logger.debug(
            "Creating custom conversation manager: import_path=%s",
            conversation_config.import_path,
        )
        return _build_custom_manager(conversation_config)

    if conversation_config.strategy not in CONVERSATION_MANAGER_REGISTRY:
        raise AgentConfigError(
            f"Invalid conversation manager type: {conversation_config.strategy}",
            tip=f"Use a valid strategy: {list(CONVERSATION_MANAGER_REGISTRY.keys())} or 'custom'.",
        )

    logger.debug("Creating conversation manager: strategy=%s", conversation_config.strategy)

    config = conversation_config.config
    builder = CONVERSATION_MANAGER_REGISTRY[conversation_config.strategy]
    return builder(config)
