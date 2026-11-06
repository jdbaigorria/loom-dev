"""L2 — ``TurnMetrics``: typed per-turn projection of Strands' metrics summary.

The fixture mirrors a real Bedrock ``get_summary()`` (Strands 1.62) with the message
content replaced by block names: only the structure and the numbers matter.
"""

import pytest

from loom.adapters.strands import Agent, Model, tool
from loom.metrics import Cycle, ModelCall, ToolCall, TurnMetrics, turn_metrics, turn_metrics_of


def _model_trace(seconds, latency_ms, first_token_ms, blocks=("text",)):
    return {
        "name": "stream_messages",
        "duration": seconds,
        "metadata": {},
        "children": [],
        "message": {
            "role": "assistant",
            "content": [{block: "…"} for block in blocks],
            "metadata": {
                "usage": {"inputTokens": 95, "outputTokens": 263, "totalTokens": 4507},
                "metrics": {"latencyMs": latency_ms, "timeToFirstByteMs": first_token_ms},
            },
        },
    }


def _tool_trace(name, tool_use_id, seconds, status="success"):
    return {
        "name": f"Tool: {name}",
        "duration": seconds,
        "metadata": {"toolUseId": tool_use_id, "tool_name": name},
        "children": [],
        "message": {
            "role": "user",
            "content": [{"toolResult": {"toolUseId": tool_use_id, "status": status}}],
        },
    }


def _cycle(name, seconds, *children):
    return {
        "name": name,
        "duration": seconds,
        "metadata": {},
        "children": list(children),
        "message": None,
    }


REAL_SUMMARY = {
    "total_cycles": 2,
    "total_duration": 8.008,
    "traces": [
        _cycle(
            "Cycle 1",
            4.175,
            _model_trace(3.13, 2037, 3129, blocks=("reasoningContent", "toolUse")),
            _tool_trace("search_providers", "tooluse_1", 1.043),
            {"name": "Recursive call", "duration": 3.833, "metadata": {}, "children": []},
        ),
        _cycle(
            "Cycle 2", 3.833, _model_trace(3.832, 3308, 3828, blocks=("reasoningContent", "text"))
        ),
    ],
    "agent_invocations": [
        {
            "usage": {
                "inputTokens": 1031,
                "outputTokens": 791,
                "totalTokens": 10120,
                "cacheReadInputTokens": 4149,
                "cacheWriteInputTokens": 4149,
                "cacheDetails": [{"ttl": "5m", "inputTokens": 4149}],
            },
            "cycles": [],
        }
    ],
}


class TestRealSummary:
    def test_cycles_model_and_tools(self):
        turn = turn_metrics(REAL_SUMMARY)

        assert turn.cycles == (
            Cycle(
                total_ms=4175,
                model=ModelCall(total_ms=3130, latency_ms=2037, first_token_ms=3129),
                tools=(
                    ToolCall(
                        tool_use_id="tooluse_1",
                        name="search_providers",
                        elapsed_ms=1043,
                        status="success",
                    ),
                ),
            ),
            Cycle(
                total_ms=3833,
                model=ModelCall(total_ms=3832, latency_ms=3308, first_token_ms=3828),
                tools=(),
            ),
        )

    def test_totals_do_not_count_the_recursive_call_twice(self):
        turn = turn_metrics(REAL_SUMMARY)

        assert (turn.duration_ms, turn.model_ms, turn.tools_ms) == (8008, 6962, 1043)
        assert turn.other_ms == 8008 - 6962 - 1043

    def test_usage_is_the_last_invocation_numbers_only(self):
        assert turn_metrics(REAL_SUMMARY).usage == {
            "inputTokens": 1031,
            "outputTokens": 791,
            "totalTokens": 10120,
            "cacheReadInputTokens": 4149,
            "cacheWriteInputTokens": 4149,
        }

    def test_never_carries_message_text(self):
        assert "…" not in turn_metrics(REAL_SUMMARY).model_dump_json()


class TestShapes:
    def test_one_cycle_without_tools(self):
        turn = turn_metrics({"traces": [_cycle("Cycle 1", 1.5, _model_trace(1.4, 1300, 900))]})

        assert turn.tools_ms == 0
        assert turn.cycles[0].tools == ()
        assert turn.other_ms == 100

    def test_two_tools_in_parallel(self):
        turn = turn_metrics(
            {
                "traces": [
                    _cycle(
                        "Cycle 1",
                        2.0,
                        _model_trace(1.0, 900, 500),
                        _tool_trace("a", "t1", 0.8),
                        _tool_trace("b", "t2", 0.6),
                    )
                ]
            }
        )

        assert [call.name for call in turn.cycles[0].tools] == ["a", "b"]
        # Parallel tools overlap: their sum may exceed the wall clock, so other_ms floors at 0.
        assert turn.tools_ms == 1400
        assert turn.other_ms == 0

    def test_since_trace_drops_earlier_turns(self):
        summary = {
            **REAL_SUMMARY,
            "traces": [_cycle("Cycle 1", 9.0, _model_trace(9.0, 1, 1)), *REAL_SUMMARY["traces"]],
        }

        assert turn_metrics(summary, since_trace=1).cycles == turn_metrics(REAL_SUMMARY).cycles

    def test_tool_error_is_counted_and_marked(self):
        turn = turn_metrics(
            {
                "traces": [
                    _cycle(
                        "Cycle 1",
                        1.0,
                        _tool_trace("search", "t1", 0.2, status="error"),
                        _tool_trace("search", "t2", 0.2),
                    )
                ]
            }
        )

        assert [call.status for call in turn.cycles[0].tools] == ["error", "success"]
        assert turn.tool_errors == {"search": 1}

    def test_unfinished_cycle_keeps_its_finished_tools(self):
        # A turn that failed mid-cycle: the cycle never ended, the tool did.
        unfinished = {**_cycle("Cycle 1", None, _tool_trace("search", "t1", 0.3)), "duration": None}

        cycle = turn_metrics({"traces": [unfinished]}).cycles[0]

        assert cycle.complete is False
        assert cycle.total_ms == 300
        assert cycle.tools[0].name == "search"

    def test_tool_without_result_message_has_no_status(self):
        trace = {**_tool_trace("ask", "t1", 0.1), "message": None}

        assert (
            turn_metrics({"traces": [_cycle("Cycle 1", 0.2, trace)]}).cycles[0].tools[0].status
            is None
        )


class TestTolerance:
    def test_empty_summary_is_all_zeros(self):
        assert turn_metrics({}) == TurnMetrics()

    @pytest.mark.parametrize(
        "traces",
        [
            "not a list",
            [None, 3, "x"],
            [{"name": "Cycle 1", "duration": "slow", "children": "nope"}],
            [
                {
                    "name": "Cycle 1",
                    "duration": 1.0,
                    "children": [None, {"metadata": "bad", "duration": True}],
                }
            ],
            [
                _cycle(
                    "Cycle 1",
                    1.0,
                    {**_model_trace(0.5, 1, 1), "message": {"metadata": {"metrics": "bad"}}},
                )
            ],
        ],
    )
    def test_malformed_traces_do_not_raise(self, traces):
        turn_metrics({"traces": traces, "agent_invocations": "bad"})

    def test_frozen(self):
        with pytest.raises(Exception):
            turn_metrics(REAL_SUMMARY).duration_ms = 0  # type: ignore[misc]


@tool
def get_time() -> str:
    """Return the time."""
    return "12:00"


class ToolThenText(Model):
    """Network-free model: asks for ``get_time`` once, then answers."""

    def __init__(self) -> None:
        self.calls = 0

    def update_config(self, **model_config):
        pass

    def get_config(self):
        return {}

    def structured_output(self, *args, **kwargs):
        raise NotImplementedError

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.calls += 1
        if self.calls % 2 == 1:
            events = [
                {"messageStart": {"role": "assistant"}},
                {
                    "contentBlockStart": {
                        "start": {"toolUse": {"toolUseId": f"t{self.calls}", "name": "get_time"}}
                    }
                },
                {"contentBlockDelta": {"delta": {"toolUse": {"input": "{}"}}}},
                {"contentBlockStop": {}},
                {"messageStop": {"stopReason": "tool_use"}},
            ]
        else:
            events = [
                {"messageStart": {"role": "assistant"}},
                {"contentBlockDelta": {"delta": {"text": "noon"}}},
                {"contentBlockStop": {}},
                {"messageStop": {"stopReason": "end_turn"}},
            ]
        for event in events:
            yield event


class TestRealAgent:
    """Drives a real Strands agent so a change in the trace shape fails here."""

    def test_reused_agent_measures_only_the_turn(self):
        agent = Agent(model=ToolThenText(), tools=[get_time], callback_handler=None)
        agent("what time is it?")
        since = len(agent.event_loop_metrics.traces)
        agent("and now?")

        turn = turn_metrics_of(agent, since_trace=since)

        assert len(turn.cycles) == 2
        assert [call.name for call in turn.cycles[0].tools] == ["get_time"]
        assert turn.cycles[0].tools[0].status == "success"
        assert turn.cycles[0].model is not None
        assert turn.duration_ms >= turn.model_ms


class TestResponseMetadata:
    def test_run_and_record_fills_turn_with_only_this_turn(self, monkeypatch):
        from loom.core import response as response_mod
        from loom.schemas.context import LoomSession

        monkeypatch.setattr(response_mod, "save_invocation", lambda *a, **k: None)
        agent = Agent(model=ToolThenText(), tools=[get_time], callback_handler=None)
        session = LoomSession(session_id="s", user_id="u")
        kwargs = {"model_id": None, "name": "a", "system_prompt_tokens": 0}

        first, _ = response_mod.run_and_record(agent, "time?", session, **kwargs)
        second, _ = response_mod.run_and_record(agent, "again?", session, **kwargs)

        assert len(first.metadata.turn.cycles) == 2
        assert len(second.metadata.turn.cycles) == 2
        assert second.metadata.turn.cycles[0].tools[0].tool_use_id == "t3"

    def test_turn_is_exported_from_loom(self):
        import loom

        assert loom.TurnMetrics is TurnMetrics
        assert loom.turn_metrics is turn_metrics
