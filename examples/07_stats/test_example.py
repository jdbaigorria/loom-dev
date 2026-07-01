"""Tests for Example 07 — Stats service."""

import json
from pathlib import Path

from loom import LoomSession
from loom.dev import run_dev
from loom.services.stats_service import aggregate, load_stats


def _session(session_id: str = "s-1", user_id: str = "u-1") -> LoomSession:
    return LoomSession(session_id=session_id, user_id=user_id)


def _write_stats(stats_file: Path, records: list[dict]) -> None:
    """Helper: write fake JSONL records directly to the stats file."""
    stats_file.parent.mkdir(parents=True, exist_ok=True)
    with stats_file.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


class TestStatsIntegration:
    def test_stats_file_created_on_run(self, loom_env):
        """A dev run creates .loom/stats/assistant.jsonl automatically."""
        run_dev("assistant", "q", _session())

        stats_file = loom_env["paths"].root / ".loom" / "stats" / "assistant.jsonl"
        assert stats_file.exists()

    def test_multiple_runs_append_multiple_records(self, loom_env):
        """Three runs produce three JSONL lines."""
        run_dev("assistant", "q", _session(session_id="s-1"))
        run_dev("assistant", "q", _session(session_id="s-2"))
        run_dev("assistant", "q", _session(session_id="s-3"))

        stats_file = loom_env["paths"].root / ".loom" / "stats" / "assistant.jsonl"
        lines = [line for line in stats_file.read_text().splitlines() if line.strip()]
        assert len(lines) == 3


class TestLoadStats:
    def test_returns_empty_list_for_nonexistent_file(self, tmp_path):
        """load_stats() returns [] when the file doesn't exist."""
        result = load_stats(tmp_path / "nonexistent.jsonl")
        assert result == []

    def test_loads_valid_records(self, tmp_path):
        """load_stats() parses all valid JSON lines."""
        stats_file = tmp_path / "stats.jsonl"
        records = [
            {"ts": "2026-01-01T00:00:00+00:00", "total_tokens": 100},
            {"ts": "2026-01-02T00:00:00+00:00", "total_tokens": 200},
        ]
        _write_stats(stats_file, records)
        result = load_stats(stats_file)
        assert len(result) == 2
        assert result[0]["total_tokens"] == 100

    def test_skips_malformed_lines(self, tmp_path):
        """load_stats() silently skips lines that are not valid JSON."""
        stats_file = tmp_path / "stats.jsonl"
        stats_file.parent.mkdir(parents=True, exist_ok=True)
        stats_file.write_text('{"total_tokens": 100}\nNOT VALID JSON\n{"total_tokens": 200}\n')
        result = load_stats(stats_file)
        assert len(result) == 2

    def test_skips_blank_lines(self, tmp_path):
        """load_stats() ignores blank lines without error."""
        stats_file = tmp_path / "stats.jsonl"
        stats_file.parent.mkdir(parents=True, exist_ok=True)
        stats_file.write_text('\n{"total_tokens": 50}\n\n')
        result = load_stats(stats_file)
        assert len(result) == 1


class TestAggregate:
    def _make_records(self, n: int, input_t: int = 10, output_t: int = 5, latency: float = 100.0):
        return [
            {
                "ts": f"2026-01-0{i + 1}T00:00:00+00:00",
                "session_id": f"s-{i}",
                "input_tokens": input_t,
                "output_tokens": output_t,
                "total_tokens": input_t + output_t,
                "response_time_ms": latency,
                "tool_calls": [],
                "system_prompt_tokens": 50,
            }
            for i in range(n)
        ]

    def test_empty_records_returns_zero_invocations(self):
        """aggregate([]) returns {'invocations': 0}."""
        assert aggregate([]) == {"invocations": 0}

    def test_invocation_count(self):
        """aggregate() reports the correct number of records."""
        records = self._make_records(3)
        assert aggregate(records)["invocations"] == 3

    def test_total_tokens(self):
        """Total tokens is the sum across all records."""
        records = self._make_records(3, input_t=10, output_t=5)
        summary = aggregate(records)
        assert summary["total_tokens"] == 45  # 3 * 15

    def test_avg_input_tokens(self):
        """avg_input_tokens is rounded integer average."""
        records = self._make_records(4, input_t=10)
        assert aggregate(records)["avg_input_tokens"] == 10

    def test_avg_response_time(self):
        """avg_response_time_ms is rounded to 1 decimal."""
        records = self._make_records(2, latency=100.0)
        assert aggregate(records)["avg_response_time_ms"] == 100.0

    def test_last_invocation_is_latest_ts(self):
        """last_invocation is the ISO timestamp of the most recent record."""
        records = self._make_records(3)
        summary = aggregate(records)
        assert summary["last_invocation"] == "2026-01-03T00:00:00+00:00"

    def test_top_tools_counted(self):
        """top_tools returns the most-used tools across all invocations."""
        records = [
            {
                "ts": "2026-01-01T00:00:00+00:00",
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "response_time_ms": 0,
                "tool_calls": ["search", "calc"],
            },
            {
                "ts": "2026-01-02T00:00:00+00:00",
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "response_time_ms": 0,
                "tool_calls": ["search"],
            },
        ]
        summary = aggregate(records)
        tool_names = [name for name, _ in summary["top_tools"]]
        assert "search" in tool_names
        # search appears twice, should rank first
        assert summary["top_tools"][0][0] == "search"
        assert summary["top_tools"][0][1] == 2
