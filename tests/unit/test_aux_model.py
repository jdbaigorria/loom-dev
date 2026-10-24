"""aux_model is a single model, built with the same overlay as the primary."""

import pytest
from pydantic import ValidationError

from loom.core.builder import build
from loom.core.exceptions import AgentConfigError
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig
from loom.schemas.context import LoomSession
from loom.testing import MockModel


def _agent(**extra) -> AgentConfig:
    base = {"name": "a", "system_prompt": {"prompt": "hi", "is_resolved": True}}
    base.update(extra)
    return AgentConfig(**base)


def test_aux_model_is_passed_to_the_agent(monkeypatch):
    primary = MockModel(["ok"])
    side = MockModel(["side"])

    def _models(model, overlay=None):
        assert overlay == {"region": "us-east-1"}
        return side if model == "economic" else primary

    monkeypatch.setattr("loom.core.builder.get_model", _models)
    agent = build(
        _agent(aux_model="economic"),
        LoomSession(session_id="s", user_id="u"),
        app_config=AppConfig(conversation="none"),
        model_params={"region": "us-east-1"},
    )
    assert agent.model is primary
    assert agent.aux_model is side


def test_aux_model_rejects_a_list():
    with pytest.raises(ValidationError, match="aux_model"):
        _agent(aux_model=["economic", "powerful"])


def test_aux_model_rejects_a_fallback_profile(monkeypatch):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    monkeypatch.setattr("loom.core.builder.is_router_model", lambda model: model == "resilient")
    with pytest.raises(AgentConfigError, match="aux_model"):
        build(
            _agent(aux_model="resilient"),
            LoomSession(session_id="s", user_id="u"),
            app_config=AppConfig(conversation="none"),
        )


def test_bidi_rejects_aux_model():
    with pytest.raises(ValidationError, match="aux_model"):
        AgentConfig(name="voice", kind="bidi", aux_model="economic")
