from typing import Any

from pydantic import BaseModel, Field


class InterruptInfo(BaseModel):
    """A pending human-in-the-loop interrupt raised by a tool during execution.

    When ``AgentResponse.interrupts`` is non-empty the agent paused waiting for
    input; resume natively by feeding interrupt-response content back to the same
    live agent (``agent([{"interruptResponse": {"interruptId": id, "response": ...}}])``).
    """

    id: str
    name: str = ""
    reason: Any = None


class AgentResponseMetadata(BaseModel):
    session_id: str
    user_id: str
    user_msg_idx: int
    assistant_msg_idx: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    response_time_ms: float
    model_id: str | None = None
    model_attempts: list[dict] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    raw_metrics: dict | None = None


class AgentResponse(BaseModel):
    answer: str
    metadata: AgentResponseMetadata
    interrupts: list[InterruptInfo] = Field(default_factory=list)
    # Experimental. Set when stop_reason is "checkpoint". Does not include the
    # conversation; resume with a session manager if you need that state.
    checkpoint: dict | None = None
