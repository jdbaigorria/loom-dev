"""Sandboxes are constructed without starting Docker or opening SSH."""

import pytest
from pydantic import ValidationError

from loom.adapters.strands import DockerSandbox, SshSandbox
from loom.core.builder import build
from loom.core.paths import WorkspacePaths
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig
from loom.schemas.context import LoomSession
from loom.testing import MockModel


def test_docker_sandbox_is_passed_to_the_agent_and_local_storage(monkeypatch, tmp_path):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    paths = WorkspacePaths(project_root=tmp_path, workspace_name="warp")
    agent = build(
        AgentConfig(
            name="a",
            system_prompt={"prompt": "hi", "is_resolved": True},
            conversation="none",
        ),
        LoomSession(session_id="s", user_id="u"),
        app_config=AppConfig(
            conversation="none",
            sandbox={"docker": {"container": "loom-runner"}},
            storage={"local": {}},
        ),
        paths=paths,
    )
    assert isinstance(agent.sandbox, DockerSandbox)
    assert agent.storage._sandbox is agent.sandbox


def test_ssh_keeps_the_secure_defaults():
    from loom.core.loaders.sandbox import get_sandbox
    from loom.schemas.config.sandbox import SandboxConfig

    sandbox = get_sandbox(
        SandboxConfig.model_validate(
            {"ssh": {"host": "runner.internal", "working_dir": "/srv/agent"}}
        )
    )
    assert isinstance(sandbox, SshSandbox)
    assert sandbox._allow_unknown_hosts is False
    assert sandbox._ssh_options == []


def test_agent_sandbox_overrides_the_app(monkeypatch):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    agent = build(
        AgentConfig(
            name="a",
            system_prompt={"prompt": "hi", "is_resolved": True},
            conversation="none",
            sandbox={"docker": {"container": "agent-runner"}},
        ),
        LoomSession(session_id="s", user_id="u"),
        app_config=AppConfig(
            conversation="none",
            sandbox={"docker": {"container": "app-runner"}},
        ),
    )
    assert agent.sandbox.container == "agent-runner"


def test_bidi_rejects_an_agent_sandbox():
    with pytest.raises(ValidationError, match="sandbox"):
        AgentConfig(name="voice", kind="bidi", sandbox={"docker": {"container": "loom-runner"}})
