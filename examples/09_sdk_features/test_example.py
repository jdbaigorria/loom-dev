"""The example YAML builds a real Agent. No Bedrock, no Docker daemon."""

from .example import build_features


def test_yaml_opts_into_sdk_fields(tmp_path):
    agent = build_features(tmp_path)

    assert agent.model._responses == ["from primary"]
    assert agent.aux_model._responses == ["from aux"]
    assert "strands:goal-loop" in agent._plugin_registry._plugins
    assert agent.memory_manager._stores[0].description == "Facts about ada in session-001"
    assert agent._intervention_registry.handlers
    assert agent._background_tasks is not None
    assert agent._checkpointing is True
    assert agent.sandbox.container == "loom-runner"
    assert agent.storage is not None
    assert agent.trace_attributes == {
        "app": "examples",
        "session.id": "from-yaml",
        "user.id": "ada",
    }
    agent.cleanup()
