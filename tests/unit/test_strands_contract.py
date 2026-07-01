"""Contract tests for the Strands ``AgentResult`` shape that Loom depends on.

Unlike ``test_loom_agent.py`` (which uses a hand-built ``MagicMock`` result and
therefore stays green even if Strands changes the real shape), these tests drive
a **real** ``strands.Agent`` with the network-free ``MockModel`` and assert the
exact structure Loom reads in ``loom.core.response.build_metadata`` /
``build_response`` and in the built-in hooks.

If Strands changes the result contract, the specific assumption that broke fails
here with a clear name — an early signal to update ``loom.core.response`` rather
than a silent metrics regression in production. The nightly ``strands-compat``
workflow runs this against the latest Strands.

Every field referenced below is consumed by Loom:
- ``result.message["content"][0]["text"]`` — ``loom.core.response.build_response``
- ``result.stop_reason``                    — ``hooks.logging_hook``
- ``result.metrics.get_summary()`` keys     — ``loom.core.response.build_metadata``
  (``accumulated_usage.{inputTokens,outputTokens,totalTokens}``,
  ``total_duration``, ``tool_usage``)
"""

import pytest

from loom.adapters.strands import Agent, AgentResult
from loom.testing import MockModel


@pytest.fixture
def result() -> AgentResult:
    """A real AgentResult produced by a real Agent + network-free MockModel."""
    agent = Agent(
        model=MockModel(["hello world"]),
        system_prompt="contract test",
        callback_handler=None,
    )
    return agent("hi")


class TestResultType:
    def test_call_returns_agent_result(self, result):
        assert isinstance(result, AgentResult)


class TestMessageShape:
    """Contract behind loom.core.response.build_response."""

    def test_message_is_dict_with_content(self, result):
        assert isinstance(result.message, dict)
        assert "content" in result.message

    def test_first_content_block_has_text(self, result):
        content = result.message["content"]
        assert isinstance(content, list) and content
        assert content[0].get("text") == "hello world"


class TestStopReason:
    """Contract behind hooks.logging_hook (event.result.stop_reason)."""

    def test_stop_reason_is_present(self, result):
        assert isinstance(result.stop_reason, str)
        assert result.stop_reason


class TestMetricsSummary:
    """Contract behind loom.core.response.build_metadata."""

    def test_get_summary_returns_dict(self, result):
        assert isinstance(result.metrics.get_summary(), dict)

    def test_accumulated_usage_token_fields(self, result):
        usage = result.metrics.get_summary()["accumulated_usage"]
        for field in ("inputTokens", "outputTokens", "totalTokens"):
            assert isinstance(usage[field], int), f"{field} must be int"

    def test_total_duration_is_numeric(self, result):
        duration = result.metrics.get_summary()["total_duration"]
        assert isinstance(duration, (int, float))

    def test_tool_usage_is_a_mapping(self, result):
        # Loom calls .keys() on this to populate AgentResponseMetadata.tool_calls.
        tool_usage = result.metrics.get_summary()["tool_usage"]
        assert isinstance(tool_usage, dict)
        assert list(tool_usage.keys()) == list(tool_usage.keys())
