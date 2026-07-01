"""Tests for Example 01 — Simple run (dev executor)."""

import json

from loom import LoomSession
from loom.dev import DevRun, run_dev


def _session(session_id: str = "s-1", user_id: str = "u-1") -> LoomSession:
    return LoomSession(session_id=session_id, user_id=user_id)


class TestSimpleRun:
    def test_returns_dev_run(self, loom_env):
        """run_dev returns a DevRun (shaped response + the built agent)."""
        run = run_dev("assistant", "What is the capital of France?", _session())
        assert isinstance(run, DevRun)

    def test_answer_is_the_model_text(self, loom_env):
        """run.response.answer carries the model's text."""
        loom_env["strands_result"][0].message = {"content": [{"text": "Paris"}]}
        run = run_dev("assistant", "q", _session())
        assert run.response.answer == "Paris"

    def test_metadata_reflects_session(self, loom_env):
        """Metadata carries the session_id and user_id from the run's session."""
        run = run_dev("assistant", "q", _session(session_id="my-session", user_id="my-user"))
        assert run.response.metadata.session_id == "my-session"
        assert run.response.metadata.user_id == "my-user"

    def test_metadata_token_counts(self, loom_env, make_result):
        """Metadata reflects token usage reported by the LLM."""
        loom_env["strands_result"][0] = make_result(input_tokens=100, output_tokens=50)
        run = run_dev("assistant", "q", _session())
        assert run.response.metadata.input_tokens == 100
        assert run.response.metadata.output_tokens == 50
        assert run.response.metadata.total_tokens == 150

    def test_metadata_latency(self, loom_env, make_result):
        """Metadata reflects response time reported by Strands."""
        loom_env["strands_result"][0] = make_result(latency=350.0)
        run = run_dev("assistant", "q", _session())
        assert run.response.metadata.response_time_ms == 350.0

    def test_stats_file_created_after_run(self, loom_env):
        """Each dev run appends a JSON record to .loom/stats/{name}.jsonl."""
        run_dev("assistant", "q", _session())
        stats_file = loom_env["paths"].root / ".loom" / "stats" / "assistant.jsonl"
        assert stats_file.exists()

    def test_stats_record_fields(self, loom_env, make_result):
        """The JSONL record contains all expected fields."""
        loom_env["strands_result"][0] = make_result(
            input_tokens=100, output_tokens=50, latency=200.0
        )
        run_dev("assistant", "q", _session(session_id="s-stats"))

        stats_file = loom_env["paths"].root / ".loom" / "stats" / "assistant.jsonl"
        record = json.loads(stats_file.read_text().strip())

        assert record["session_id"] == "s-stats"
        assert "ts" in record
        # Strands metrics summary is persisted verbatim under "metrics".
        usage = record["metrics"]["accumulated_usage"]
        assert usage["inputTokens"] == 100
        assert usage["outputTokens"] == 50
        assert usage["totalTokens"] == 150
        assert record["metrics"]["total_duration"] == 200.0
