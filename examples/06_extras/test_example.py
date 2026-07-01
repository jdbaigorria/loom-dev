"""Tests for Example 06 — Passing extras as native invocation_state."""

from types import SimpleNamespace

from loom import LoomSession
from loom.dev import run_dev

from .tools.tenant_tool import get_tenant_info


def _session(session_id: str = "s-1", user_id: str = "u-1") -> LoomSession:
    return LoomSession(session_id=session_id, user_id=user_id)


class TestExtras:
    def test_extras_forwarded_as_invocation_state(self, loom_env):
        """run_dev(extras=...) reaches the agent as native invocation_state."""
        run_dev(
            "assistant",
            "q",
            _session(),
            extras={"tenant_id": "acme-corp", "jwt": {"sub": "user-123", "roles": ["admin"]}},
        )

        _, kwargs = loom_env["mock_strands"].call_args
        assert kwargs["invocation_state"]["tenant_id"] == "acme-corp"
        assert kwargs["invocation_state"]["jwt"]["sub"] == "user-123"

    def test_empty_extras_is_valid(self, loom_env):
        """Running with no extras forwards an empty invocation_state, no error."""
        run = run_dev("assistant", "q", _session())
        assert run.response.answer is not None
        _, kwargs = loom_env["mock_strands"].call_args
        assert kwargs["invocation_state"] == {}

    def test_extras_do_not_leak_into_answer(self, loom_env):
        """Extras are context only — they don't appear in the response text."""
        loom_env["strands_result"][0].message = {"content": [{"text": "Here is the info"}]}
        run = run_dev("assistant", "q", _session(), extras={"secret_key": "super-secret-value"})
        assert "super-secret-value" not in run.response.answer

    def test_tool_reads_invocation_state(self):
        """The migrated tool reads context from tool_context.invocation_state."""
        ctx = SimpleNamespace(
            invocation_state={"tenant_id": "acme-corp", "jwt": {"sub": "user-123"}}
        )
        result = get_tenant_info.__wrapped__(tool_context=ctx)
        assert result["tenant_id"] == "acme-corp"
        assert result["jwt_sub"] == "user-123"

    def test_tool_falls_back_to_defaults(self):
        """Missing keys fall back to safe defaults."""
        ctx = SimpleNamespace(invocation_state={})
        result = get_tenant_info.__wrapped__(tool_context=ctx)
        assert result["tenant_id"] == "unknown"
        assert result["user_role"] == "guest"
        assert result["jwt_sub"] == "anonymous"
