"""L5 — built-in ``metrics`` hook: TurnMetrics per invocation, handed to a sink."""

import io
import json
import logging
import sys
import textwrap
from types import SimpleNamespace

import pytest

from loom.adapters.strands import Agent
from loom.core.builder import build
from loom.core.exceptions import AgentConfigError, HookLoadError
from loom.core.loaders.hook import get_hooks
from loom.hooks.metrics import MetricsHook
from loom.metrics import ModelSettings, TurnContext, TurnMetrics
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig
from loom.schemas.config.hook import HookConfig
from loom.schemas.context import LoomSession
from loom.testing import MockModel

CYCLE = {
    "name": "Cycle 1",
    "duration": 1.0,
    "metadata": {},
    "children": [
        {"name": "stream_messages", "duration": 0.6, "metadata": {}, "children": []},
        {
            "name": "Tool: search",
            "duration": 0.3,
            "metadata": {"toolUseId": "t1", "tool_name": "search"},
            "children": [],
            "message": {"content": [{"toolResult": {"status": "error"}}]},
        },
    ],
}
SUMMARY = {
    "traces": [CYCLE],
    "agent_invocations": [{"usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15}}],
}


class _Metrics:
    def __init__(self, summary):
        self.summary = summary
        self.traces = list(summary.get("traces", []))

    def get_summary(self):
        return self.summary


def _event(summary=SUMMARY, *, result=SimpleNamespace(stop_reason="end_turn"), name="support"):
    agent = SimpleNamespace(name=name, event_loop_metrics=_Metrics(summary))
    return SimpleNamespace(agent=agent, result=result, invocation_state={})


@pytest.fixture
def sink_module(tmp_path, monkeypatch):
    (tmp_path / "acme_metrics.py").write_text(
        textwrap.dedent(
            """
            received = []


            def publish(metrics, context):
                received.append((metrics, context))


            NOT_CALLABLE = 3
            """
        )
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    import acme_metrics

    acme_metrics.received.clear()
    yield acme_metrics
    sys.modules.pop("acme_metrics", None)


def _run(hook, event):
    hook._mark(SimpleNamespace(agent=SimpleNamespace(event_loop_metrics=_Metrics({}))))
    hook._emit(event)


class TestSinkCallable:
    def test_ok_turn(self, sink_module):
        hook = MetricsHook(sink="acme_metrics:publish")
        hook.loom_bind(agent="support", session=LoomSession(session_id="s", user_id="u"))

        _run(hook, _event())

        ((metrics, context),) = sink_module.received
        assert isinstance(metrics, TurnMetrics)
        assert metrics.tool_errors == {"search": 1}
        assert context == TurnContext(
            agent="support",
            session_id="s",
            user_id="u",
            outcome="ok",
            stop_reason="end_turn",
            # The fake agent has no model: an empty description (L6).
            model_settings=ModelSettings(),
        )

    def test_failed_turn_reports_what_ran(self, sink_module):
        hook = MetricsHook(sink="acme_metrics.publish")

        _run(hook, _event(result=None))

        ((metrics, context),) = sink_module.received
        assert context.outcome == "error"
        assert context.stop_reason is None
        assert context.session_id is None
        assert [t.name for t in metrics.cycles[0].tools] == ["search"]

    def test_reused_agent_reports_only_the_turn(self, sink_module):
        hook = MetricsHook(sink="acme_metrics:publish")
        earlier = {**CYCLE, "name": "Cycle 0"}
        summary = {**SUMMARY, "traces": [earlier, CYCLE]}
        hook._mark(
            SimpleNamespace(
                agent=SimpleNamespace(event_loop_metrics=_Metrics({"traces": [earlier]}))
            )
        )

        hook._emit(_event(summary))

        ((metrics, _),) = sink_module.received
        assert len(metrics.cycles) == 1

    def test_a_failing_sink_does_not_break_the_turn(self, caplog):
        hook = MetricsHook(sink="log")
        hook._send = lambda metrics, context: 1 / 0

        with caplog.at_level(logging.WARNING, logger="loom.hooks.metrics"):
            _run(hook, _event())

        assert "metrics hook failed" in caplog.text

    def test_unknown_callable_is_a_load_error(self):
        with pytest.raises(HookLoadError):
            MetricsHook(sink="acme_nope:publish")

    def test_non_callable_is_a_load_error(self, sink_module):
        with pytest.raises(HookLoadError, match="callable"):
            MetricsHook(sink="acme_metrics:NOT_CALLABLE")


class TestSinkLog:
    def test_one_info_line_with_extra(self, caplog):
        with caplog.at_level(logging.INFO, logger="loom.metrics"):
            _run(MetricsHook(), _event())

        (record,) = [r for r in caplog.records if r.name == "loom.metrics"]
        assert "agent=support" in record.getMessage()
        assert record.turn["tool_errors"] == {"search": 1}
        assert record.context["outcome"] == "ok"

    def test_silent_when_the_host_did_not_enable_info(self, caplog):
        with caplog.at_level(logging.WARNING, logger="loom.metrics"):
            _run(MetricsHook(), _event())

        assert not [r for r in caplog.records if r.name == "loom.metrics"]


def _emf_lines(capsys, hook, event):
    _run(hook, event)
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


class TestSinkEmf:
    def test_turn_line_and_one_line_per_tool(self, capsys):
        hook = MetricsHook(sink="emf", namespace="Acme/Agents", service="acme")
        hook.loom_bind(agent="support", session=LoomSession(session_id="s", user_id="u"))

        turn, tool = _emf_lines(capsys, hook, _event())

        spec = turn["_aws"]["CloudWatchMetrics"][0]
        assert spec["Namespace"] == "Acme/Agents"
        assert spec["Dimensions"] == [["agent", "service"]]
        assert isinstance(turn["_aws"]["Timestamp"], int) and turn["_aws"]["Timestamp"] > 10**12
        names = [m["Name"] for m in spec["Metrics"]]
        assert names == [
            "Invocations",
            "InvocationErrors",
            "InvocationDuration",
            "InputTokens",
            "OutputTokens",
            "TotalTokens",
            "ModelDuration",
            "ToolsDuration",
            "OtherDuration",
            "Cycles",
        ]
        assert all(name in turn for name in names)
        assert (turn["Invocations"], turn["InvocationErrors"], turn["TotalTokens"]) == (1, 0, 15)
        assert (turn["agent"], turn["service"], turn["session_id"], turn["outcome"]) == (
            "support",
            "acme",
            "s",
            "ok",
        )
        assert tool["_aws"]["CloudWatchMetrics"][0]["Dimensions"] == [["agent", "tool", "service"]]
        assert (
            tool["tool"],
            tool["ToolDuration"],
            tool["ToolInvocations"],
            tool["ToolErrors"],
        ) == (
            "search",
            300,
            1,
            1,
        )

    def test_session_and_user_are_never_dimensions(self, capsys):
        hook = MetricsHook(sink="emf", namespace="Acme/Agents")
        hook.loom_bind(agent="support", session=LoomSession(session_id="s", user_id="u"))

        for line in _emf_lines(capsys, hook, _event()):
            dims = line["_aws"]["CloudWatchMetrics"][0]["Dimensions"][0]
            assert "session_id" not in dims and "user_id" not in dims

    def test_failed_turn_has_errors_and_no_tokens(self, capsys):
        turn, _ = _emf_lines(capsys, MetricsHook(sink="emf", namespace="A"), _event(result=None))

        assert turn["InvocationErrors"] == 1
        assert "TotalTokens" not in turn

    def test_include_tools_only(self, capsys):
        lines = _emf_lines(
            capsys, MetricsHook(sink="emf", namespace="A", include=["tools"]), _event()
        )

        assert len(lines) == 1
        assert "Invocations" not in lines[0]
        assert lines[0]["tool"] == "search"

    def test_include_breakdown_only_has_no_counts(self, capsys):
        (turn,) = _emf_lines(
            capsys, MetricsHook(sink="emf", namespace="A", include=["breakdown"]), _event()
        )

        assert "ModelDuration" in turn
        assert "Invocations" not in turn and "TotalTokens" not in turn

    def test_writes_to_the_current_stdout(self, monkeypatch):
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)

        _run(MetricsHook(sink="emf", namespace="A"), _event())

        assert '"_aws"' in out.getvalue()


class TestParams:
    @pytest.mark.parametrize(
        "params",
        [
            {"sink": "nope"},
            {"sink": "emf"},
            {"sink": "emf", "namespace": ""},
            {"sink": "log", "namespace": "A"},
            {"sink": "log", "include": ["tools"]},
            {"sink": "emf", "namespace": "A", "include": ["everything"]},
            {"sink": "emf", "namespace": "A", "include": []},
            {"enabled": "maybe"},
        ],
    )
    def test_invalid_params_are_load_errors(self, params):
        with pytest.raises(HookLoadError):
            MetricsHook(**params)

    def test_unknown_param_through_the_loader(self):
        with pytest.raises(HookLoadError):
            get_hooks([HookConfig.model_validate({"metrics": {"colour": "red"}})], None)

    @pytest.mark.parametrize("value", [False, "false", "0", "no", "OFF"])
    def test_disabled_registers_nothing(self, value):
        agent = Agent(
            model=MockModel(["ok"]), hooks=[MetricsHook(enabled=value)], callback_handler=None
        )

        callbacks = agent.hooks.get_callbacks_for(_after(agent))
        assert not [
            cb for cb in callbacks if isinstance(getattr(cb, "__self__", None), MetricsHook)
        ]

    def test_enabled_accepts_strings_from_env_interpolation(self):
        hook = MetricsHook(enabled="true")
        agent = Agent(model=MockModel(["ok"]), hooks=[hook], callback_handler=None)

        callbacks = agent.hooks.get_callbacks_for(_after(agent))
        assert [cb for cb in callbacks if getattr(cb, "__self__", None) is hook]


def _after(agent):
    from loom.adapters.strands import AfterInvocationEvent

    return AfterInvocationEvent(agent=agent, invocation_state={})


def _config(**extra) -> AgentConfig:
    base = {"name": "support", "system_prompt": {"prompt": "hi", "is_resolved": True}}
    base.update(extra)
    return AgentConfig(**base)


class TestBuilder:
    def test_builtin_is_registered_and_bound(self, monkeypatch, sink_module):
        monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
        agent = build(
            _config(hooks=[{"metrics": {"sink": "acme_metrics:publish"}}]),
            LoomSession(session_id="s", user_id="u"),
            app_config=AppConfig(conversation="none"),
        )

        agent("hi")

        ((metrics, context),) = sink_module.received
        assert (context.agent, context.session_id, context.user_id) == ("support", "s", "u")
        assert context.outcome == "ok"
        assert metrics.cycles

    def test_user_hook_with_loom_bind_gets_the_session(self, monkeypatch, tmp_path):
        (tmp_path / "who_hook.py").write_text(
            textwrap.dedent(
                """
                from strands.hooks import HookProvider


                class WhoHook(HookProvider):
                    bound = None

                    def loom_bind(self, *, agent, session):
                        self.bound = (agent, session.session_id)

                    def register_hooks(self, registry, **kwargs):
                        pass
                """
            )
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
        built = {}
        real_get_hooks = get_hooks

        def spy(defs, hooks_dir):
            built["hooks"] = real_get_hooks(defs, hooks_dir)
            return built["hooks"]

        monkeypatch.setattr("loom.core.builder.get_hooks", spy)
        build(
            _config(hooks=["who_hook:WhoHook"]),
            LoomSession(session_id="s", user_id="u"),
            app_config=AppConfig(conversation="none"),
        )

        assert built["hooks"][0].bound == ("support", "s")
        sys.modules.pop("who_hook", None)

    def test_bidi_rejects_the_metrics_hook(self, monkeypatch):
        monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
        with pytest.raises(AgentConfigError, match="metrics"):
            build(
                _config(kind="bidi", hooks=["metrics"]),
                LoomSession(session_id="s", user_id="u"),
                app_config=AppConfig(conversation="none"),
            )
