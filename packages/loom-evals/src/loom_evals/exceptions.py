"""Evaluation errors. They are not part of ``loom.errors``."""

from loom.core.exceptions import LoomError


class EvalsError(LoomError):
    """Base class for errors related to evaluations."""


class EvalsNotFoundError(EvalsError):
    """Raised when no evals.yml file exists for an agent."""

    def __init__(self, name: str = "", tip: str | None = None):
        msg = f"No evals found for agent '{name}'." if name else "Evals not found."
        super().__init__(
            msg,
            tip=tip or f"Create a evals.yml file in warp/agents/{name}/evals/",
        )


class EvalsAlreadyExistsError(EvalsError):
    """Raised when an evals.yml file already exists for the agent."""

    def __init__(self, name: str = "", tip: str | None = None):
        msg = f"Evals already exist for agent '{name}'." if name else "Evals already exist."
        super().__init__(
            msg,
            tip=tip or "Remove the existing evals.yml or edit it directly.",
        )


class EvalsRunError(EvalsError):
    """Raised when the evaluation execution fails."""

    def __init__(self, message: str, tip: str | None = None):
        super().__init__(message, tip=tip)
