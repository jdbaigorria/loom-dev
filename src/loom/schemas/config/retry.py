"""Retry configuration: a profile name or an inline tuning block.

Opinionated retry profiles (``low`` / ``medium`` / ``high`` and any project-defined
ones) live in ``loom.config.profiles``, not hardcoded here. An agent refers to a
profile by name or inlines its own ``RetryConfig``::

    retry: low                               # profile name

    retry: { max_attempts: 6, initial_delay: 2, max_delay: 120 }   # inline
"""

from typing import Self

from pydantic import BaseModel, model_validator


class RetryConfig(BaseModel):
    """Tuning parameters for a model retry strategy."""

    max_attempts: int = 3
    initial_delay: float = 0.1
    max_delay: float = 1.0

    @model_validator(mode="after")
    def validate_delays(self) -> Self:
        """Ensure initial_delay does not exceed max_delay."""
        if self.initial_delay > self.max_delay:
            raise ValueError(
                f"The initial delay ({self.initial_delay}s) cannot be "
                f"greater than the max delay ({self.max_delay}s)"
            )
        return self


# A retry is either a profile name (str) or an inline tuning block.
RetryStrategyConfig = str | RetryConfig
