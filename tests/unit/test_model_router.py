"""Model fallback via the real Strands ModelRouter, without network calls."""

import pytest
from pydantic import ValidationError

from loom.adapters.strands import Agent, ModelRouter
from loom.core.exceptions import AgentConfigError
from loom.core.loaders.model import get_model
from loom.core.loaders.routing import RoutingTraceHook
from loom.schemas.config.models import CustomModelConfig, FallbackModelConfig
from loom.testing import FailingModel, MockModel


def test_fallback_config_requires_two_candidates():
    with pytest.raises(ValidationError):
        FallbackModelConfig(fallback=["only"])


def test_duplicate_model_id_is_rejected():
    cfg = FallbackModelConfig(
        fallback=[
            CustomModelConfig(
                import_path="loom.testing.MockModel", name="a", params={"model_id": "same"}
            ),
            CustomModelConfig(
                import_path="loom.testing.MockModel", name="b", params={"model_id": "same"}
            ),
        ]
    )
    with pytest.raises(AgentConfigError, match="model_id"):
        get_model(cfg)


def test_router_answers_with_the_backup_when_the_primary_fails():
    cfg = [
        CustomModelConfig(import_path="loom.testing.FailingModel", name="primario"),
        CustomModelConfig(
            import_path="loom.testing.MockModel",
            name="respaldo",
            params={"responses": ["from backup"]},
        ),
    ]
    model = get_model(cfg)
    assert isinstance(model, ModelRouter)
    trace = RoutingTraceHook()
    agent = Agent(model=model, callback_handler=None, hooks=[trace])
    result = agent("hi")
    assert result.message["content"][0]["text"] == "from backup"
    assert [item["candidate"] for item in trace.attempts] == ["primario", "respaldo"]
    assert trace.attempts[-1]["outcome"] == "OK"


def test_router_propagates_when_every_candidate_fails():
    cfg = FallbackModelConfig(
        fallback=[
            CustomModelConfig(import_path="loom.testing.FailingModel", name="a"),
            CustomModelConfig(import_path="loom.testing.FailingModel", name="b"),
        ]
    )
    agent = Agent(model=get_model(cfg), callback_handler=None)
    with pytest.raises(RuntimeError, match="primary failed"):
        agent("hi")


def test_profile_fallback_matches_an_inline_list(monkeypatch):
    from loom.config.profiles import Profiles
    from loom.core.loaders import model as model_loader

    profiles = Profiles(
        model={
            "one": CustomModelConfig(
                import_path="loom.testing.MockModel", params={"responses": ["a"]}
            ),
            "two": CustomModelConfig(
                import_path="loom.testing.MockModel", params={"responses": ["b"]}
            ),
            "resilient": FallbackModelConfig(fallback=["one", "two"]),
        }
    )
    monkeypatch.setattr(model_loader, "get_profiles", lambda: profiles)
    built = get_model("resilient")
    assert isinstance(built, ModelRouter)


def test_mock_models_are_distinct_classes_for_the_overlay_guard():
    assert FailingModel is not MockModel
