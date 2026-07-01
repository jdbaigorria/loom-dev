"""Tests for Example 02 — Multi-turn conversation (hold a native agent)."""

import loom
from loom import LoomSession


def _session(session_id: str = "conv-1", user_id: str = "u-1") -> LoomSession:
    return LoomSession(session_id=session_id, user_id=user_id)


class TestConversation:
    def test_build_agent_returns_a_native_agent(self, loom_env):
        """build_agent returns a native strands.Agent you hold across turns."""
        agent = loom.build_agent("assistant", _session())
        assert agent is loom_env["mock_strands"]

    def test_messages_grow_with_each_turn(self, loom_env):
        """Calling the held agent accumulates user+assistant pairs per turn."""
        agent = loom.build_agent("assistant", _session())

        agent("Turn 1")
        assert len(agent.messages) == 2  # user + assistant

        agent("Turn 2")
        assert len(agent.messages) == 4

        agent("Turn 3")
        assert len(agent.messages) == 6

    def test_agent_built_once_for_the_whole_conversation(self, loom_env):
        """One build_agent call serves the whole session — no rebuild per turn."""
        agent = loom.build_agent("assistant", _session())
        agent("Turn 1")
        agent("Turn 2")
        loom_env["mock_build_agent"].assert_called_once()

    def test_new_agent_starts_with_fresh_history(self, loom_env):
        """A second built agent starts empty (continuity is per held instance)."""
        agent_a = loom.build_agent("assistant", _session())
        agent_a("Hello from A")

        # Simulate a second instance: reset the mock's message log.
        loom_env["mock_strands"].messages = []

        agent_b = loom.build_agent("assistant", _session())
        agent_b("Hello from B")
        assert len(agent_b.messages) == 2  # only B's turn
