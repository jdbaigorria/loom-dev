"""Context strategies skip the conversation manager when they replace it."""

import pytest
from pydantic import ValidationError

from loom.core.builder import build
from loom.core.exceptions import AgentConfigError
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig
from loom.schemas.context import LoomSession
from loom.testing import MockModel


class _Stateful(MockModel):
    stateful = True


def _agent(**extra) -> AgentConfig:
    base = {"name": "a", "system_prompt": {"prompt": "hi", "is_resolved": True}}
    base.update(extra)
    return AgentConfig(**base)


def _session() -> LoomSession:
    return LoomSession(session_id="s", user_id="u")


def test_context_off_does_not_install_a_conversation_manager(monkeypatch):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *args, **kwargs: MockModel(["ok"]))

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("conversation_manager must not be built")

    monkeypatch.setattr("loom.core.builder.get_conversation_manager", _forbidden)
    agent = build(
        _agent(context="off", conversation="none"),
        _session(),
        app_config=AppConfig(conversation="none"),
    )
    assert agent("hi").message["content"][0]["text"] == "ok"


def test_context_rejects_a_real_conversation_strategy():
    with pytest.raises(AgentConfigError, match="conversation"):
        build(
            _agent(context="auto", conversation="sliding"),
            _session(),
            app_config=AppConfig(conversation="none"),
        )


def test_stateful_model_rejects_a_conversation_strategy(monkeypatch):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *args, **kwargs: _Stateful(["ok"]))
    with pytest.raises(AgentConfigError, match="stateful"):
        build(
            _agent(conversation="sliding"),
            _session(),
            app_config=AppConfig(conversation="none"),
        )


def test_bidi_rejects_context():
    with pytest.raises(ValidationError, match="context"):
        AgentConfig(name="voice", kind="bidi", context="auto")
