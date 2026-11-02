"""L6 — the model, its whitelisted settings and the variant in TurnContext and the sinks."""

import json
import logging
import sys
import textwrap
from types import SimpleNamespace

import pytest

from loom.adapters.strands import Agent
from loom.core.builder import build
from loom.core.loaders.model import get_model
from loom.hooks.metrics import MetricsHook
from loom.metrics import (
    ModelDescription,
    ModelSettings,
    describe_model,
    variant_of,
)
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig
from loom.schemas.config.models import CustomModelConfig
from loom.schemas.context import LoomSession
from loom.testing import MockModel

BEDROCK_CONFIG = {
    "model_id": "us.anthropic.claude-haiku-5-5",
    "max_tokens": 8000,
    "streaming": False,
    "include_tool_result_status": "auto",
    "guardrail_id": "gr-123",
    "guardrail_version": "2",
    "stop_sequences": ["END"],
    "additional_request_fields": {
        "thinking": {"type": "enabled", "budget_tokens": 2048},
        "output_config": {"effort": "low"},
        "anthropic_beta": ["interleaved-thinking"],
    },
}


class _Configured(MockModel):
    """MockModel whose get_config returns a provider-shaped config."""

    def __init__(self, config: dict, responses: list[str] | None = None) -> None:
        super().__init__(responses or ["ok"])
        self._config = config

    def get_config(self):
        return self._config

    @property
    def model_id(self):
        return self._config.get("model_id")


def _agent(config: dict, *, system_prompt_content=None, labels=None, trace=None):
    return SimpleNamespace(
        model=_Configured(config),
        system_prompt_content=system_prompt_content,
        _loom_labels=labels,
        _loom_routing_trace=trace,
    )


class TestDescribeModel:
    def test_bedrock_whitelist(self):
        description = describe_model(_agent({**BEDROCK_CONFIG, "boto_session": object()}))

        assert description.model_id == "us.anthropic.claude-haiku-5-5"
        assert description.settings == ModelSettings(
            max_tokens=8000,
            streaming=False,
            thinking="enabled",
            thinking_budget=2048,
            effort="low",
            prompt_cache=False,
            guardrail=True,
        )
        dumped = json.dumps(description.model_dump())
        for secret in ("anthropic_beta", "boto_session", "gr-123", "END", "include_tool"):
            assert secret not in dumped

    def test_openai_style_params(self):
        config = {
            "model_id": "gpt-5",
            "params": {
                "max_completion_tokens": 900,
                "temperature": 0.2,
                "reasoning_effort": "medium",
                "api_key": "sk-secret",
            },
            "client_args": {"api_key": "sk-secret"},
        }

        description = describe_model(_agent(config))

        assert (description.settings.max_tokens, description.settings.temperature) == (900, 0.2)
        assert description.settings.effort == "medium"
        assert "sk-secret" not in json.dumps(description.model_dump())

    def test_nova_reasoning_config(self):
        config = {
            "model_id": "us.amazon.nova-premier",
            "additional_request_fields": {
                "reasoningConfig": {"type": "enabled", "maxReasoningEffort": "high"}
            },
        }

        settings = describe_model(_agent(config)).settings

        assert (settings.thinking, settings.effort) == ("enabled", "high")

    @pytest.mark.parametrize(
        ("config", "field"),
        [
            ({"additional_request_fields": {"output_config": {"effort": {"x": 1}}}}, "effort"),
            ({"temperature": "0.2"}, "temperature"),
            ({"max_tokens": True}, "max_tokens"),
            ({"streaming": "yes"}, "streaming"),
        ],
    )
    def test_wrong_types_are_dropped(self, config, field):
        assert getattr(describe_model(_agent(config)).settings, field) is None

    def test_int_temperature_is_a_float(self):
        assert describe_model(_agent({"temperature": 1})).settings.temperature == 1.0

    def test_prompt_cache_from_the_system_prompt(self):
        agent = _agent(
            {"model_id": "m"}, system_prompt_content=[{"text": "hi"}, {"cachePoint": {}}]
        )

        assert describe_model(agent).settings.prompt_cache is True

    def test_prompt_cache_from_cache_config(self):
        assert describe_model(_agent({"cache_config": {"strategy": "auto"}})).settings.prompt_cache

    def test_falls_back_to_the_model_id_attribute(self):
        agent = SimpleNamespace(model=MockModel(["ok"]))

        assert describe_model(agent).model_id == "mock"

    def test_never_raises(self):
        class Broken:
            def get_config(self):
                raise RuntimeError("boom")

        assert describe_model(SimpleNamespace(model=Broken())) == ModelDescription()
        assert describe_model(object()) == ModelDescription()


class TestVariant:
    @pytest.mark.parametrize(
        ("labels", "expected"),
        [
            ({"metrics.variant": "effort-low"}, "effort-low"),
            ({"metrics.variant": 2}, "2"),
            ({"metrics.variant": True}, "true"),
            ({"metrics.variant": ["a", "b"]}, None),
            ({"areas": ["x"]}, None),
            (None, None),
        ],
    )
    def test_variant_of(self, labels, expected):
        assert variant_of(SimpleNamespace(_loom_labels=labels)) == expected

    def test_builder_keeps_labels_and_warns_on_a_list_variant(self, monkeypatch, caplog):
        monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
        config = AgentConfig(
            name="a",
            system_prompt={"prompt": "hi", "is_resolved": True},
            labels={"metrics.variant": ["x", "y"], "areas": ["z"]},
        )

        with caplog.at_level(logging.WARNING, logger="loom.core.builder"):
            agent = build(
                config,
                LoomSession(session_id="s", user_id="u"),
                app_config=AppConfig(conversation="none"),
            )

        assert variant_of(agent) is None
        assert "metrics.variant" in caplog.text


@pytest.fixture
def router_models(tmp_path, monkeypatch):
    (tmp_path / "acme_models.py").write_text(
        textwrap.dedent(
            """
            from loom.testing import FailingModel, MockModel


            class Primary(FailingModel):
                def get_config(self):
                    return {"model_id": "primary-model", "max_tokens": 100}


            class Backup(MockModel):
                def __init__(self, **kwargs):
                    super().__init__(["from backup"])

                def get_config(self):
                    return {"model_id": "backup-model", "max_tokens": 200}
            """
        )
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    yield
    sys.modules.pop("acme_models", None)


class TestRouter:
    def test_the_model_that_answered_with_its_own_settings(self, router_models, monkeypatch):
        received = []
        monkeypatch.setattr(
            "loom.hooks.metrics.log_sink", lambda metrics, context: received.append(context)
        )
        router = get_model(
            [
                CustomModelConfig(import_path="acme_models.Primary", name="primario"),
                CustomModelConfig(import_path="acme_models.Backup", name="respaldo"),
            ]
        )
        monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: router)
        config = AgentConfig(
            name="a", system_prompt={"prompt": "hi", "is_resolved": True}, hooks=["metrics"]
        )
        agent = build(
            config,
            LoomSession(session_id="s", user_id="u"),
            app_config=AppConfig(conversation="none"),
        )

        agent("hi")

        (context,) = received
        assert (context.model_id, context.model_fallbacks) == ("backup-model", 1)
        assert context.model_settings.max_tokens == 200


def _emf(capsys, hook, agent):
    hook._mark(SimpleNamespace(agent=agent))
    hook._emit(SimpleNamespace(agent=agent, result=SimpleNamespace(stop_reason="end_turn")))
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def _real_agent(labels=None, config=None):
    agent = Agent(model=_Configured(config or BEDROCK_CONFIG), callback_handler=None)
    agent._loom_labels = labels or {}
    return agent


class TestEmf:
    def _hook(self):
        hook = MetricsHook(sink="emf", namespace="A", service="acme")
        hook.loom_bind(agent="support", session=LoomSession(session_id="s", user_id="u"))
        return hook

    def test_model_and_variant_dimension_sets(self, capsys):
        agent = _real_agent({"metrics.variant": "effort-low"})
        agent("hi")

        (line,) = _emf(capsys, self._hook(), agent)

        assert line["_aws"]["CloudWatchMetrics"][0]["Dimensions"] == [
            ["agent", "service"],
            ["agent", "model", "service"],
            ["agent", "variant", "service"],
        ]
        assert (line["model"], line["variant"]) == ("us.anthropic.claude-haiku-5-5", "effort-low")
        assert line["model_config"] == {
            "max_tokens": 8000,
            "streaming": False,
            "effort": "low",
            "thinking": "enabled",
            "thinking_budget": 2048,
            "prompt_cache": False,
            "guardrail": True,
        }
        assert line["model_fallbacks"] == 0

    def test_without_variant_two_sets(self, capsys):
        agent = _real_agent()
        agent("hi")

        (line,) = _emf(capsys, self._hook(), agent)

        assert len(line["_aws"]["CloudWatchMetrics"][0]["Dimensions"]) == 2
        assert "variant" not in line

    def test_without_model_one_set(self, capsys):
        agent = _real_agent(config={"max_tokens": 5})

        (line,) = _emf(capsys, self._hook(), agent)

        assert line["_aws"]["CloudWatchMetrics"][0]["Dimensions"] == [["agent", "service"]]

    def test_tool_lines_keep_their_dimensions_and_carry_the_model(self, capsys):
        hook = self._hook()
        agent = _real_agent({"metrics.variant": "v1"})
        tool_trace = {
            "name": "Cycle 1",
            "duration": 1.0,
            "children": [
                {
                    "name": "Tool: s",
                    "duration": 0.2,
                    "metadata": {"tool_name": "s", "toolUseId": "t"},
                }
            ],
        }
        agent.event_loop_metrics.get_summary = lambda: {"traces": [tool_trace]}  # type: ignore[method-assign]

        _, tool = _emf(capsys, hook, agent)

        assert tool["_aws"]["CloudWatchMetrics"][0]["Dimensions"] == [["agent", "tool", "service"]]
        assert (tool["model"], tool["variant"]) == ("us.anthropic.claude-haiku-5-5", "v1")
        assert tool["model_config"]["max_tokens"] == 8000


class TestLogSink:
    def test_message_names_the_model(self, caplog):
        agent = _real_agent()
        agent("hi")
        hook = MetricsHook()

        with caplog.at_level(logging.INFO, logger="loom.metrics"):
            hook._mark(SimpleNamespace(agent=agent))
            hook._emit(SimpleNamespace(agent=agent, result=SimpleNamespace(stop_reason="end_turn")))

        (record,) = [r for r in caplog.records if r.name == "loom.metrics"]
        assert "model=us.anthropic.claude-haiku-5-5" in record.getMessage()
        assert record.context["model_settings"]["effort"] == "low"
