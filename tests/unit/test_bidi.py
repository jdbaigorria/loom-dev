"""Tests for the experimental bidi (full-duplex) kind: build path + discovery."""

from unittest.mock import MagicMock, patch

import pytest

from loom.adapters.config import FileConfigSource
from loom.core.builder import build
from loom.core.exceptions import AgentConfigError, LoomError
from loom.core.paths import WorkspacePaths
from loom.schemas.config.agent import AgentConfig
from loom.schemas.context import LoomSession


def _session() -> LoomSession:
    return LoomSession(session_id="s", user_id="u")


class TestBuildBidi:
    def test_build_bidi_uses_bidiagent_and_omits_agent_only_params(self):
        """kind=bidi builds via BidiAgent without conv-mgr/structured/retry/callback."""
        cfg = AgentConfig(name="voice", kind="bidi")
        fake_bidi = MagicMock()
        with (
            patch("loom.core.builder.get_model", return_value="MODEL"),
            patch("loom.core.builder.get_prompt", return_value="PROMPT"),
            patch("loom.core.builder.sx.BidiAgent", fake_bidi),
        ):
            agent = build(cfg, _session())

        assert agent is fake_bidi.return_value
        _, kwargs = fake_bidi.call_args
        assert kwargs["model"] == "MODEL"
        assert "conversation_manager" not in kwargs
        assert "structured_output_model" not in kwargs
        assert "retry_strategy" not in kwargs
        assert "callback_handler" not in kwargs

    def test_tool_executor_is_rejected_before_bidi_is_built(self):
        cfg = AgentConfig(name="voice", kind="bidi", tool_executor="sequential")
        fake_bidi = MagicMock()
        with patch("loom.core.builder.sx.BidiAgent", fake_bidi):
            with pytest.raises(AgentConfigError, match="tool_executor"):
                from loom.core.builder import _build_bidi

                _build_bidi(cfg, {"tool_executor": object()})
        fake_bidi.assert_not_called()

    def test_build_bidi_missing_capability_raises(self):
        """kind=bidi on a Strands without BidiAgent → friendly error."""
        cfg = AgentConfig(name="voice", kind="bidi")
        with (
            patch("loom.core.builder.get_model", return_value="MODEL"),
            patch("loom.core.builder.get_prompt", return_value="PROMPT"),
            patch("loom.core.builder.sx.BidiAgent", None),
        ):
            with pytest.raises(AgentConfigError, match="BidiAgent"):
                build(cfg, _session())


class TestBidiDiscovery:
    def test_discovery_reports_bidi_kind(self, tmp_path):
        """An agent declaring kind: bidi is surfaced as a 'bidi' target."""
        ws = WorkspacePaths(project_root=tmp_path, workspace_name="warp")
        cfg = ws.agent("voice").yaml_file
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text("name: voice\nkind: bidi\ndescription: Voice agent\n", encoding="utf-8")

        src = FileConfigSource(workspace=ws)
        targets = {t.name: t for t in src.list_targets()}
        assert targets["voice"].kind == "bidi"
        assert targets["voice"].description == "Voice agent"
        assert src.get_target_kind("voice") == "bidi"


class TestRunDevRejectsBidi:
    def test_run_dev_refuses_bidi(self):
        """run_dev is one-shot; a bidi target must go through the harness stream."""
        from loom.dev import run_dev

        with patch("loom.dev._resolve_kind", return_value="bidi"):
            with pytest.raises(LoomError, match="full-duplex"):
                run_dev("voice", "hi", _session())
