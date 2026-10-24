"""Memory stores resolve session placeholders and reach a real Agent."""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from loom.adapters.strands import FileMemoryStore, MemoryManager
from loom.core.builder import build
from loom.core.paths import WorkspacePaths
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig
from loom.schemas.context import LoomSession
from loom.testing import MockModel


def test_file_store_resolves_placeholders_and_is_attached(monkeypatch, tmp_path):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    paths = WorkspacePaths(project_root=tmp_path, workspace_name="warp")
    agent = build(
        AgentConfig(
            name="a",
            system_prompt={"prompt": "hi", "is_resolved": True},
            conversation="none",
            memory={
                "stores": [
                    {"file": {"name": "notes", "description": "for {user_id} in {session_id}"}}
                ]
            },
        ),
        LoomSession(session_id="sess-1", user_id="ada"),
        app_config=AppConfig(conversation="none"),
        paths=paths,
    )
    assert isinstance(agent.memory_manager, MemoryManager)
    store = agent.memory_manager._stores[0]
    assert isinstance(store, FileMemoryStore)
    assert store.description == "for ada in sess-1"


def test_bedrock_store_uses_the_overlay_session(monkeypatch):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    def _client(service, region_name=None):
        return runtime if service == "bedrock-agent-runtime" else agent_client

    runtime = MagicMock()
    agent_client = MagicMock()
    boto = MagicMock()
    boto.client.side_effect = _client
    agent = build(
        AgentConfig(
            name="a",
            system_prompt={"prompt": "hi", "is_resolved": True},
            conversation="none",
            memory={
                "stores": [
                    {
                        "bedrock_kb": {
                            "name": "policies",
                            "scope": "{user_id}",
                            "config": {
                                "knowledge_base_id": "KB1",
                                "knowledge_base_type": "VECTOR",
                            },
                        }
                    }
                ]
            },
        ),
        LoomSession(session_id="s", user_id="ada"),
        app_config=AppConfig(conversation="none"),
        model_params={"boto_session": boto},
    )
    store = agent.memory_manager._stores[0]
    assert store.scope == "ada"
    assert store._runtime_client is runtime
    boto.client.assert_any_call("bedrock-agent-runtime", region_name=None)


def test_bidi_rejects_memory():
    with pytest.raises(ValidationError, match="memory"):
        AgentConfig(
            name="voice",
            kind="bidi",
            memory={"stores": [{"file": {"name": "notes"}}]},
        )
