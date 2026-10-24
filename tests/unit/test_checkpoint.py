"""Experimental checkpoints are copied onto AgentResponse and resumed by the CLI."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from loom.core.builder import build
from loom.core.response import build_response
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig
from loom.schemas.context import LoomSession
from loom.schemas.response import AgentResponse, AgentResponseMetadata
from loom.testing import MockModel


def _metadata() -> AgentResponseMetadata:
    return AgentResponseMetadata(
        session_id="s",
        user_id="u",
        user_msg_idx=0,
        assistant_msg_idx=0,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        response_time_ms=0,
    )


def test_build_response_keeps_a_checkpoint():
    marker = {"position": "after_model", "cycle_index": 0, "schema_version": "1.0"}
    result = SimpleNamespace(
        message={"content": [{"text": "paused"}]},
        metrics=SimpleNamespace(get_summary=lambda: {}),
        interrupts=[],
        stop_reason="checkpoint",
        checkpoint=SimpleNamespace(to_dict=lambda: marker),
    )
    response = build_response(
        result,
        LoomSession(session_id="s", user_id="u"),
        model_id=None,
        user_msg_idx=0,
        assistant_msg_idx=0,
    )
    assert response.checkpoint == marker
    assert response.answer == "paused"


def test_cli_resumes_until_the_checkpoint_clears(monkeypatch):
    from loom.cli.commands import run as run_cmd

    marker = {"position": "after_tools", "cycle_index": 1, "schema_version": "1.0"}
    paused = AgentResponse(answer="wait", metadata=_metadata(), checkpoint=marker)
    done = AgentResponse(answer="finished", metadata=_metadata())
    seen: list = []

    def _turn(_dev, content, _session):
        seen.append(content)
        return (done, False)

    monkeypatch.setattr(run_cmd, "run_turn", _turn)
    monkeypatch.setattr(run_cmd, "print_hint", lambda *_a, **_k: None)
    response = run_cmd.resolve_checkpoints(
        SimpleNamespace(), LoomSession(session_id="s", user_id="u"), paused
    )
    assert seen == [{"checkpointResume": {"checkpoint": marker}}]
    assert response.answer == "finished"
    assert response.checkpoint is None


def test_agent_receives_checkpointing(monkeypatch):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    agent = build(
        AgentConfig(
            name="a",
            system_prompt={"prompt": "hi", "is_resolved": True},
            conversation="none",
            checkpointing=True,
        ),
        LoomSession(session_id="s", user_id="u"),
        app_config=AppConfig(conversation="none"),
    )
    assert agent._checkpointing is True


def test_bidi_rejects_checkpointing():
    with pytest.raises(ValidationError, match="checkpointing"):
        AgentConfig(name="voice", kind="bidi", checkpointing=True)
