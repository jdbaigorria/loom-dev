"""output accepts a class path plus an optional structured-output prompt."""

from pydantic import BaseModel

from loom.core.builder import build
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig
from loom.schemas.context import LoomSession
from loom.testing import MockModel


class Answer(BaseModel):
    text: str


def test_output_prompt_reaches_the_agent(monkeypatch):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    agent = build(
        AgentConfig(
            name="a",
            system_prompt={"prompt": "hi", "is_resolved": True},
            output={"class": "tests.unit.test_structured_output:Answer", "prompt": "Be brief."},
        ),
        LoomSession(session_id="s", user_id="u"),
        app_config=AppConfig(conversation="none"),
    )
    assert agent._structured_output_prompt == "Be brief."
    assert agent._default_structured_output_model is Answer
