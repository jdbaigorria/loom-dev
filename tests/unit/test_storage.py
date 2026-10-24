"""Shared storage is built only when app.yml declares it, including for bidi."""

from unittest.mock import MagicMock, patch

from loom.adapters.strands import InMemoryStorage, LocalFileStorage, S3Storage
from loom.core.builder import build
from loom.core.paths import WorkspacePaths
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig
from loom.schemas.context import LoomSession
from loom.testing import MockModel


def _agent() -> AgentConfig:
    return AgentConfig(
        name="a",
        system_prompt={"prompt": "hi", "is_resolved": True},
        conversation="none",
    )


def test_local_storage_uses_the_metadata_dir(monkeypatch, tmp_path):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    paths = WorkspacePaths(project_root=tmp_path, workspace_name="warp")
    agent = build(
        _agent(),
        LoomSession(session_id="s", user_id="u"),
        app_config=AppConfig(conversation="none", storage={"local": {}}),
        paths=paths,
    )
    assert isinstance(agent.storage, LocalFileStorage)
    assert str(paths.metadata_dir / "storage") == str(agent.storage.base_dir)


def test_memory_storage_and_s3_session(monkeypatch):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    sentinel = object()
    agent = build(
        _agent(),
        LoomSession(session_id="s", user_id="u"),
        app_config=AppConfig(conversation="none", storage="memory"),
        model_params={"boto_session": sentinel},
    )
    assert isinstance(agent.storage, InMemoryStorage)

    s3 = build(
        _agent(),
        LoomSession(session_id="s", user_id="u"),
        app_config=AppConfig(
            conversation="none",
            storage={"s3": {"bucket": "loom-bucket", "prefix": "loom/"}},
        ),
        model_params={"boto_session": sentinel},
    )
    assert isinstance(s3.storage, S3Storage)
    assert s3.storage._bucket == "loom-bucket"
    assert s3.storage._boto_session is sentinel


def test_bidi_receives_storage():
    cfg = AgentConfig(name="voice", kind="bidi")
    fake = MagicMock()
    with (
        patch("loom.core.builder.get_model", return_value="MODEL"),
        patch("loom.core.builder.get_prompt", return_value="PROMPT"),
        patch("loom.core.builder.sx.BidiAgent", fake),
    ):
        build(
            cfg,
            LoomSession(session_id="s", user_id="u"),
            app_config=AppConfig(storage="memory"),
        )
    _, kwargs = fake.call_args
    assert isinstance(kwargs["storage"], InMemoryStorage)
