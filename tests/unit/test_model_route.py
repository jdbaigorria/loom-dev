"""Classifier routing builds a ModelRouter and does not fail over."""

import pytest

from loom.core.exceptions import AgentConfigError
from loom.core.loaders.model import get_model
from loom.schemas.config.models import RouteModelConfig


def _route() -> dict:
    mock = "loom.testing.MockModel"
    return {
        "route": {
            "strategy": "classifier",
            "classifier": {"import_path": mock, "params": {"responses": ["pick"]}},
            "candidates": [
                {
                    "model": {"import_path": mock, "name": "cheap", "params": {"responses": ["a"]}},
                    "description": "short",
                },
                {
                    "model": {
                        "import_path": mock,
                        "name": "strong",
                        "params": {"responses": ["b"]},
                    },
                    "description": "long",
                },
            ],
        }
    }


def test_route_builds_a_classifier_router():
    router = get_model(RouteModelConfig.model_validate(_route()))
    assert type(router._strategy).__name__ == "ClassifierStrategy"
    assert [candidate.name for candidate in router._candidates] == ["cheap", "strong"]


def test_route_rejects_duplicate_names():
    raw = _route()
    raw["route"]["candidates"][1]["model"]["name"] = "cheap"
    with pytest.raises(AgentConfigError, match="unique"):
        get_model(RouteModelConfig.model_validate(raw))
