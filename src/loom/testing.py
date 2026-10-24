"""loom.testing — Utilities for testing LOOM-based agents without hitting real LLMs.

Provides :class:`MockModel` (a fake ``strands.Model`` that returns predefined
text responses) and the :func:`mock_llm` context manager that wires it into the
LOOM build pipeline so no real network calls are made during tests.

Usage::

    from loom.testing import mock_llm

    with mock_llm("Hello!", "How can I help?") as model:
        response = agent.invoke(request)

    assert "Hello" in response.answer
    assert model.call_count == 1
"""

import logging
from collections.abc import AsyncGenerator, AsyncIterable
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

from pydantic import BaseModel

from loom.adapters.strands import (
    Messages,
    Model,
    StreamEvent,
    SystemContentBlock,
    ToolChoice,
    ToolSpec,
)

logger = logging.getLogger(__name__)


class MockModel(Model):
    """Fake LLM model that cycles through predefined text responses.

    Useful in tests to avoid real network calls to Bedrock / OpenAI / Gemini.
    The model cycles through the response list when it runs out of entries.

    Args:
        responses: Ordered list of strings to return.  Cycles when exhausted.
            Defaults to ``["Mock response"]`` when *None* or empty.

    Attributes:
        call_count: Number of times :meth:`stream` has been called.

    Example::

        model = MockModel(["Hello!", "How can I help?"])
        # 1st stream call → "Hello!"
        # 2nd stream call → "How can I help?"
        # 3rd stream call → "Hello!"  (cycles)
    """

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses: list[str] = responses if responses else ["Mock response"]
        self.call_count: int = 0

    @property
    def model_id(self) -> str:
        """Identifier reported in :class:`~loom.schemas.response.AgentResponseMetadata`."""
        return "mock"

    def _next_response(self) -> str:
        """Return the next predefined response (cycling)."""
        text = self._responses[self.call_count % len(self._responses)]
        self.call_count += 1
        return text

    # ── Model ABC ────────────────────────────────────────────────────────────

    def update_config(self, **model_config: Any) -> None:
        """No-op — MockModel has no configurable parameters."""

    def get_config(self) -> dict[str, Any]:
        """Return the mock configuration dict."""
        return {"provider": "mock", "responses": self._responses}

    async def structured_output(
        self,
        output_model: type[BaseModel],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict]:
        """Return a minimally-constructed output model instance.

        Args:
            output_model: Pydantic model class to instantiate.
            prompt: Unused in mock.
            system_prompt: Unused in mock.
            **kwargs: Ignored.

        Yields:
            Single dict with key ``"output"`` containing the constructed model.
        """
        text = self._next_response()
        try:
            output = output_model.model_validate_json(text)
        except Exception:
            output = output_model.model_construct()
        yield {"output": output}

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        *,
        tool_choice: ToolChoice | None = None,
        system_prompt_content: list[SystemContentBlock] | None = None,
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamEvent]:
        """Yield a minimal but valid Strands streaming event sequence.

        The sequence follows the Bedrock streaming protocol:
        ``messageStart → contentBlockStart → contentBlockDelta → contentBlockStop
        → messageStop → metadata``

        Args:
            messages: Unused in mock.
            tool_specs: Unused in mock.
            system_prompt: Unused in mock.
            tool_choice: Unused in mock.
            system_prompt_content: Unused in mock.
            invocation_state: Unused in mock.
            **kwargs: Ignored.

        Yields:
            :class:`~strands.types.streaming.StreamEvent` dicts.
        """
        text = self._next_response()
        tokens = max(1, len(text.split()))

        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"contentBlockIndex": 0, "start": {}}}
        yield {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": text}}}
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {
                    "inputTokens": 10,
                    "outputTokens": tokens,
                    "totalTokens": 10 + tokens,
                },
                "metrics": {"latencyMs": 0},
            }
        }


class FailingModel(MockModel):
    """Mock model whose ``stream`` always raises. Used to exercise model fallback."""

    async def stream(self, *args: Any, **kwargs: Any) -> AsyncIterable[StreamEvent]:
        self.call_count += 1
        raise RuntimeError("primary failed")
        yield {}  # pragma: no cover


@contextmanager
def mock_llm(*responses: str):
    """Context manager that replaces the LLM with a :class:`MockModel`.

    All agents built inside this context use the mock instead of calling
    real cloud APIs.  Responses cycle automatically when exhausted.

    Args:
        *responses: Predefined text responses to cycle through.
            When none are provided, defaults to ``"Mock response"``.

    Yields:
        MockModel: The active mock model (useful for assertions on
            :attr:`~MockModel.call_count`).

    Example::

        from loom import LoomSession, build_agent
        from loom.testing import mock_llm

        with mock_llm("Hello!", "Bye!") as model:
            agent = build_agent("my_agent", LoomSession(session_id="s", user_id="u"))
            result = agent("hi")

        assert model.call_count == 1
    """
    model = MockModel(list(responses) if responses else None)
    with patch("loom.core.builder.get_model", return_value=model):
        logger.debug("mock_llm active: %d predefined response(s)", len(model._responses))
        yield model
