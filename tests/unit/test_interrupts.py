"""Tests for human-in-the-loop interrupt surfacing and (native) resume.

Interrupts are raised inside tool code during a real model-driven tool call, so
the full flow needs a live LLM; here the agent is stubbed to return results with
(or without) pending interrupts. We verify the dev executor's wiring: surfacing
them on the shaped ``AgentResponse``, reporting ``interrupted``, and resuming by
feeding interrupt-response content straight back to the same live agent.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from loom.dev import DevAgent, run_turn
from loom.schemas.context import LoomSession
from loom.schemas.response import AgentResponse, InterruptInfo


def _result(text="", interrupts=()):
    return MagicMock(
        message={"content": [{"text": text}]},
        metrics=MagicMock(get_summary=lambda: {}),
        interrupts=list(interrupts),
    )


def _dev_agent(agent) -> DevAgent:
    return DevAgent(agent=agent, model_id=None, system_prompt_tokens=0, name="a")


def _session() -> LoomSession:
    return LoomSession(session_id="s", user_id="u")


class TestInterruptSchema:
    def test_response_interrupts_default_empty(self):
        assert AgentResponse(answer="x", metadata=_fake_meta()).interrupts == []

    def test_extract_handles_dataclass_like_and_dict(self):
        from loom.core.response import extract_interrupts

        items = [
            SimpleNamespace(id="i1", name="ask", reason="why?"),
            {"id": "i2", "name": "confirm", "reason": None},
        ]
        out = extract_interrupts(MagicMock(interrupts=items))
        assert [i.id for i in out] == ["i1", "i2"]
        assert out[0].name == "ask" and out[0].reason == "why?"
        assert isinstance(out[0], InterruptInfo)


class TestRunTurnSurfacesInterrupts:
    def test_interrupt_is_surfaced_and_flagged(self):
        agent = MagicMock()
        agent.messages = []
        agent.return_value = _result(interrupts=[SimpleNamespace(id="i1", name="ask", reason="r")])

        with patch("loom.core.response.save_invocation"):
            response, interrupted = run_turn(_dev_agent(agent), "hi", _session())

        assert [i.id for i in response.interrupts] == ["i1"]
        assert interrupted is True

    def test_no_interrupt_returns_empty_list(self):
        agent = MagicMock()
        agent.messages = []
        agent.return_value = _result(text="done", interrupts=[])

        with patch("loom.core.response.save_invocation"):
            response, interrupted = run_turn(_dev_agent(agent), "hi", _session())

        assert response.interrupts == []
        assert response.answer == "done"
        assert interrupted is False


class TestNativeResume:
    def test_resume_feeds_interrupt_response_payload_to_same_agent(self):
        agent = MagicMock()
        agent.messages = []
        agent.return_value = _result(text="continued", interrupts=[])

        # The CLI builds this content from the user's answers; resume = another turn.
        interrupt_content = [
            {"interruptResponse": {"interruptId": "i1", "response": "yes"}},
            {"interruptResponse": {"interruptId": "i2", "response": "no"}},
        ]
        with patch("loom.core.response.save_invocation"):
            response, _ = run_turn(_dev_agent(agent), interrupt_content, _session())

        assert agent.call_args.args[0] == interrupt_content
        assert response.answer == "continued"


def _fake_meta():
    from loom.schemas.response import AgentResponseMetadata

    return AgentResponseMetadata(
        session_id="s",
        user_id="u",
        user_msg_idx=0,
        assistant_msg_idx=0,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        response_time_ms=0.0,
    )
