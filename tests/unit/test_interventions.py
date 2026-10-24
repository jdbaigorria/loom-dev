"""HITL attaches to a real agent; unknown tools and missing Cedar fail at build."""

import pytest
from pydantic import ValidationError

from loom.adapters.strands import HumanInTheLoop
from loom.core.builder import build
from loom.core.exceptions import AgentConfigError
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig
from loom.schemas.context import LoomSession
from loom.testing import MockModel


def _agent(**extra) -> AgentConfig:
    base = {
        "name": "a",
        "system_prompt": {"prompt": "hi", "is_resolved": True},
        "conversation": "none",
        "tools": [{"search": {}}],
    }
    base.update(extra)
    return AgentConfig(**base)


def test_hitl_is_attached_and_interrupts_when_ask_is_omitted(monkeypatch):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    monkeypatch.setattr("loom.core.builder.get_tools", lambda *a, **k: [])
    agent = build(
        _agent(interventions=[{"hitl": {"allowed_tools": ["search"]}}]),
        LoomSession(session_id="s", user_id="u"),
        app_config=AppConfig(conversation="none"),
    )
    handlers = agent._intervention_registry.handlers
    assert isinstance(handlers[0], HumanInTheLoop)
    assert handlers[0]._ask is None


def test_unknown_allowed_tool_is_rejected(monkeypatch):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    monkeypatch.setattr("loom.core.builder.get_tools", lambda *a, **k: [])
    with pytest.raises(AgentConfigError, match="allowed_tools"):
        build(
            _agent(interventions=[{"hitl": {"allowed_tools": ["missing"]}}]),
            LoomSession(session_id="s", user_id="u"),
            app_config=AppConfig(conversation="none"),
        )


def test_cedar_without_the_extra_names_the_install(monkeypatch):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    monkeypatch.setattr("loom.core.builder.get_tools", lambda *a, **k: [])
    monkeypatch.setattr("loom.core.loaders.intervention.sx.CedarAuthorization", None)
    with pytest.raises(AgentConfigError, match="cedar"):
        build(
            _agent(interventions=[{"cedar": {"policies": "permit(principal, action, resource);"}}]),
            LoomSession(session_id="s", user_id="u"),
            app_config=AppConfig(conversation="none"),
        )


def test_bidi_rejects_interventions():
    with pytest.raises(ValidationError, match="interventions"):
        AgentConfig(name="voice", kind="bidi", interventions=["hitl"])
