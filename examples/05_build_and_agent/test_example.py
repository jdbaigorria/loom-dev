"""Tests for Example 05 — build_agent() returns a native strands.Agent."""

import loom
from loom import LoomSession
from loom.dev import run_dev


def _session(session_id: str = "s-1", user_id: str = "u-1") -> LoomSession:
    return LoomSession(session_id=session_id, user_id=user_id)


class TestBuildAgent:
    def test_build_agent_returns_strands_agent(self, loom_env):
        """build_agent(name, session) hands back the native strands.Agent."""
        agent = loom.build_agent("assistant", _session())
        assert agent is loom_env["mock_strands"]

    def test_held_agent_is_called_directly(self, loom_env):
        """You drive the built agent with Strands natively — agent(query)."""
        agent = loom.build_agent("assistant", _session())
        result = agent("What is 3 + 3?")
        assert result.message["content"][0]["text"]

    def test_build_agent_called_once_per_build(self, loom_env):
        """Each build_agent call builds one agent (no hidden caching layer)."""
        loom.build_agent("assistant", _session())
        loom_env["mock_build_agent"].assert_called_once()

    def test_run_dev_exposes_the_built_agent(self, loom_env):
        """The dev executor returns the built agent on DevRun.agent for inspection."""
        run = run_dev("assistant", "hi", _session())
        assert run.agent is loom_env["mock_strands"]
