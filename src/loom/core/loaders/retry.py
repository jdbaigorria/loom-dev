"""
loom.core.loaders.retry — Build the model retry strategy.

A retry is either a **profile name** (resolved from ``loom.config.profiles`` —
built-ins ``low`` / ``medium`` / ``high`` plus any project-defined ones) or an
inline ``RetryConfig``. The opinionated profile values are no longer hardcoded
here; they live in config.
"""

import logging

from loom.adapters.strands import ModelRetryStrategy
from loom.config.profiles import get_profiles
from loom.core.exceptions import AgentConfigError
from loom.schemas.config.retry import RetryConfig, RetryStrategyConfig

logger = logging.getLogger(__name__)


def resolve_retry_config(retry: RetryStrategyConfig) -> RetryConfig:
    """Return the concrete ``RetryConfig`` for a profile name or inline config.

    Raises:
        AgentConfigError: If a profile name is not defined.
    """
    if isinstance(retry, str):
        profiles = get_profiles()
        cfg = profiles.retry.get(retry)
        if cfg is None:
            raise AgentConfigError(
                f"Unknown retry profile: '{retry}'",
                tip=f"Use one of {list(profiles.retry)} or define it in warp/config/profiles.toml.",
            )
        return cfg
    return retry


def get_retry_strategy(retry: RetryStrategyConfig) -> ModelRetryStrategy:
    """Build the retry strategy from a profile name or inline config.

    Returns:
        ``ModelRetryStrategy`` ready to pass to ``strands.Agent``.
    """
    config = resolve_retry_config(retry)
    logger.debug("Retry strategy: max_attempts=%d", config.max_attempts)
    return ModelRetryStrategy(**config.model_dump())
