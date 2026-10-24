"""Declared telemetry attributes gain session.id and user.id; user keys win."""

import pytest

from loom.core.builder import build
from loom.core.exceptions import AgentConfigError
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig
from loom.schemas.config.telemetry import TelemetryConfig
from loom.schemas.context import LoomSession
from loom.testing import MockModel


def test_session_ids_are_merged_and_user_keys_win(monkeypatch):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    agent = build(
        AgentConfig(
            name="a",
            system_prompt={"prompt": "hi", "is_resolved": True},
            conversation="none",
        ),
        LoomSession(session_id="sess-1", user_id="ada"),
        app_config=AppConfig(
            conversation="none",
            telemetry=TelemetryConfig(
                trace_attributes={"app": "billing", "session.id": "override"},
                baggage_attributes={"tenant": "acme"},
            ),
        ),
    )
    assert agent.trace_attributes["session.id"] == "override"
    assert agent.trace_attributes["user.id"] == "ada"
    assert agent.trace_attributes["app"] == "billing"
    assert agent.baggage_attributes == {
        "session.id": "sess-1",
        "user.id": "ada",
        "tenant": "acme",
    }


def test_omitted_attributes_stay_empty(monkeypatch):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    agent = build(
        AgentConfig(
            name="a",
            system_prompt={"prompt": "hi", "is_resolved": True},
            conversation="none",
        ),
        LoomSession(session_id="sess-1", user_id="ada"),
        app_config=AppConfig(conversation="none"),
    )
    assert agent.trace_attributes == {}
    assert agent.baggage_attributes == {}


def test_bidi_rejects_trace_attributes(monkeypatch):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    monkeypatch.setattr("loom.core.builder.get_prompt", lambda *a, **k: "hi")
    with pytest.raises(AgentConfigError, match="bidi"):
        build(
            AgentConfig(name="voice", kind="bidi"),
            LoomSession(session_id="s", user_id="u"),
            app_config=AppConfig(telemetry=TelemetryConfig(trace_attributes={"app": "billing"})),
        )
