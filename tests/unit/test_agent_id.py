"""agent_id: each agent keeps its own history inside a shared session.

Strands stores a session's history under ``agents/agent_<agent_id>/``. Without an
explicit id every agent is ``default``, so two agents on the same ``session_id``
(an area switch between turns, or two workflow nodes) read and overwrite one
another's messages. Loom defaults ``agent_id`` to the agent's name.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from loom.core.builder import build
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig
from loom.schemas.config.sessions import FileConfig, FileSession
from loom.schemas.context import LoomSession
from loom.testing import mock_llm


def _cfg(name: str, **extra) -> AgentConfig:
    return AgentConfig(name=name, system_prompt={"prompt": "hi", "is_resolved": True}, **extra)


def _file_app(tmp_path) -> AppConfig:
    return AppConfig(
        session=FileSession(config=FileConfig(path=str(tmp_path / "sessions"))),
        conversation="none",
    )


def _texts(agent) -> list[str]:
    return [message["content"][0]["text"] for message in agent.messages]


class TestAgentIdDefault:
    def test_agent_id_defaults_to_the_agent_name(self):
        """AID-01: without agent_id in the YAML the Strands agent is keyed by its name."""
        with mock_llm():
            agent = build(_cfg("billing"), LoomSession(session_id="s", user_id="u"))

        assert agent.agent_id == "billing"

    def test_explicit_agent_id_wins(self):
        """AID-02: agent_id in the YAML is passed through (e.g. 'default' to keep old sessions)."""
        with mock_llm():
            agent = build(
                _cfg("billing", agent_id="default"), LoomSession(session_id="s", user_id="u")
            )

        assert agent.agent_id == "default"

    @pytest.mark.parametrize("bad", ["a/b", "../x", "a\\b", ""])
    def test_agent_id_rejects_path_separators(self, bad):
        """AID-03: an agent_id that is not a single path segment fails at load time."""
        with pytest.raises(ValidationError):
            _cfg("billing", agent_id=bad)

    def test_bidi_agent_receives_agent_id(self):
        """AID-04: kind=bidi gets the same agent_id as a regular agent."""
        fake_bidi = MagicMock()
        with (
            patch("loom.core.builder.get_model", return_value="MODEL"),
            patch("loom.core.builder.sx.BidiAgent", fake_bidi),
        ):
            build(_cfg("voice", kind="bidi"), LoomSession(session_id="s", user_id="u"))

        assert fake_bidi.call_args.kwargs["agent_id"] == "voice"


class TestSharedSession:
    def test_second_agent_does_not_inherit_the_first_agents_history(self, tmp_path):
        """AID-05: switching agents on the same session_id starts a clean history."""
        app = _file_app(tmp_path)
        session = LoomSession(session_id="s1", user_id="u")

        with mock_llm("billing answer", "support answer"):
            build(_cfg("billing"), session, app_config=app)("billing question")
            support = build(_cfg("support"), session, app_config=app)

        assert support.messages == []

    def test_agents_on_one_session_do_not_overwrite_each_other(self, tmp_path):
        """AID-06: two live agents on one session keep separate message files."""
        app = _file_app(tmp_path)
        session = LoomSession(session_id="s2", user_id="u")

        with mock_llm("billing answer", "support answer"):
            billing = build(_cfg("billing"), session, app_config=app)
            support = build(_cfg("support"), session, app_config=app)
            billing("billing question")
            support("support question")

            reopened = build(_cfg("billing"), session, app_config=app)

        agents_dir = tmp_path / "sessions" / "session_s2" / "agents"
        assert sorted(p.name for p in agents_dir.iterdir()) == ["agent_billing", "agent_support"]
        assert _texts(reopened) == ["billing question", "billing answer"]
