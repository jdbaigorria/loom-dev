"""background_tasks is off unless the YAML sets it, and tool names must exist."""

import pytest
from pydantic import ValidationError

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


def test_true_enables_background_tasks(monkeypatch):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    monkeypatch.setattr("loom.core.builder.get_tools", lambda *a, **k: [])
    agent = build(
        _agent(background_tasks=True),
        LoomSession(session_id="s", user_id="u"),
        app_config=AppConfig(conversation="none"),
    )
    assert agent._background_tasks is not None


def test_unknown_background_tool_is_rejected(monkeypatch):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    monkeypatch.setattr("loom.core.builder.get_tools", lambda *a, **k: [])
    with pytest.raises(AgentConfigError, match="background_tasks"):
        build(
            _agent(background_tasks={"always": ["missing"]}),
            LoomSession(session_id="s", user_id="u"),
            app_config=AppConfig(conversation="none"),
        )


def test_bidi_rejects_background_tasks():
    with pytest.raises(ValidationError, match="background_tasks"):
        AgentConfig(name="voice", kind="bidi", background_tasks=True)
