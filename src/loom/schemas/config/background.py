"""Background tool execution declared on an agent."""

from pydantic import Field

from .strict import StrictConfig


class BackgroundTasksConfig(StrictConfig):
    """Dict form of ``background_tasks``. Names must be tools on the agent."""

    always: list[str] | None = None
    never: list[str] | None = None
    agentic: list[str] | None = None
    max_concurrency: int | None = Field(default=None, ge=1)
    timeout: float | None = Field(default=None, gt=0)
    wait_for_completion: bool | None = None
