"""Tests for catalog discovery: FileConfigSource.get_target_kind + list_targets."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from loom.adapters.config import FileConfigSource
from loom.core.exceptions import TargetResolutionError
from loom.core.paths import WorkspacePaths


def _source_with_ws(*, agent: bool = False, workflow: bool = False) -> FileConfigSource:
    """FileConfigSource over a fake workspace whose YAMLs exist per the flags."""
    ws = MagicMock()
    ws.agent.return_value.yaml_file.exists.return_value = agent
    ws.workflow_file.return_value.exists.return_value = workflow
    return FileConfigSource(workspace=ws)


class TestGetTargetKind:
    def test_solo_agente(self):
        """TGT-01: solo existe el agente → 'agent'."""
        assert _source_with_ws(agent=True).get_target_kind("x") == "agent"

    def test_solo_workflow(self):
        """TGT-02: solo existe el workflow → 'workflow'."""
        assert _source_with_ws(workflow=True).get_target_kind("x") == "workflow"

    def test_colision_sin_kind_lanza_error(self):
        """TGT-03: existe como ambos y sin kind → error pidiendo desambiguar."""
        with pytest.raises(TargetResolutionError, match="both an agent and a workflow"):
            _source_with_ws(agent=True, workflow=True).get_target_kind("x")

    def test_colision_con_kind_resuelve(self):
        """TGT-04: con kind explícito, la colisión se resuelve a ese tipo."""
        src = _source_with_ws(agent=True, workflow=True)
        assert src.get_target_kind("x", "agent") == "agent"
        assert src.get_target_kind("x", "workflow") == "workflow"

    def test_ninguno_lanza_error(self):
        """TGT-05: no existe en ningún lado → 'neither an agent nor a workflow'."""
        with pytest.raises(TargetResolutionError, match="neither an agent nor a workflow"):
            _source_with_ws().get_target_kind("x")

    def test_kind_agente_inexistente_lanza_error(self):
        """TGT-06: kind='agent' pero no hay agente → error."""
        with pytest.raises(TargetResolutionError, match="No agent"):
            _source_with_ws(workflow=True).get_target_kind("x", "agent")

    def test_kind_workflow_inexistente_lanza_error(self):
        """TGT-07: kind='workflow' pero no hay workflow → error."""
        with pytest.raises(TargetResolutionError, match="No workflow"):
            _source_with_ws(agent=True).get_target_kind("x", "workflow")


def _scaffold(root: Path, *, agents: dict[str, str], workflows: dict[str, str]) -> FileConfigSource:
    """Create a minimal workspace on disk and return a FileConfigSource over it."""
    ws = WorkspacePaths(project_root=root, workspace_name="warp")
    for name, desc in agents.items():
        cfg = ws.agent(name).yaml_file
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(f"name: {name}\ndescription: {desc}\n", encoding="utf-8")
    ws.workflows_dir.mkdir(parents=True, exist_ok=True)
    for name, desc in workflows.items():
        ws.workflow_file(name).write_text(
            f"name: {name}\ndescription: {desc}\ntype: swarm\nagents: [a]\n", encoding="utf-8"
        )
    return FileConfigSource(workspace=ws)


class TestListTargets:
    def test_lists_agents_and_workflows_with_kind_and_description(self, tmp_path):
        """DSC-01: discovery reports name + kind + description for both kinds."""
        src = _scaffold(
            tmp_path,
            agents={"billing": "Handles invoices", "support": "Answers questions"},
            workflows={"triage": "Routes tickets"},
        )
        targets = {t.name: t for t in src.list_targets()}

        assert targets["billing"].kind == "agent"
        assert targets["billing"].description == "Handles invoices"
        assert targets["support"].kind == "agent"
        assert targets["triage"].kind == "workflow"
        assert targets["triage"].description == "Routes tickets"

    def test_empty_workspace_returns_no_targets(self, tmp_path):
        """DSC-02: a workspace with no agents/workflows yields an empty catalog."""
        ws = WorkspacePaths(project_root=tmp_path, workspace_name="warp")
        assert FileConfigSource(workspace=ws).list_targets() == []

    def test_shared_tools_dir_is_not_a_target(self, tmp_path):
        """DSC-03: the agents/tools/ shared dir is not mistaken for an agent."""
        src = _scaffold(tmp_path, agents={"real": "An agent"}, workflows={})
        (src.workspace.shared_tools_dir).mkdir(parents=True, exist_ok=True)
        names = [t.name for t in src.list_targets()]
        assert names == ["real"]


class TestGetWorkflowConfig:
    def test_returns_validated_workflow_config(self, tmp_path):
        """The source resolves a workflow name to its validated config."""
        from loom.schemas.config.workflow import SwarmWorkflowConfig

        src = _scaffold(tmp_path, agents={}, workflows={"triage": "Routes tickets"})
        config = src.get_workflow_config("triage")

        assert isinstance(config, SwarmWorkflowConfig)
        assert config.name == "triage"
        assert config.description == "Routes tickets"

    def test_missing_workflow_raises(self, tmp_path):
        from loom.core.exceptions import WorkflowNotFoundError

        src = _scaffold(tmp_path, agents={}, workflows={})
        with pytest.raises(WorkflowNotFoundError):
            src.get_workflow_config("ghost")


class TestDiscoverInjection:
    def test_discover_uses_injected_source(self):
        """``loom.discover(source)`` lists from the given source, not the disk."""
        import loom
        from loom.schemas.target import TargetInfo

        catalog = [TargetInfo("a", "agent", "x")]
        source = MagicMock()
        source.list_targets.return_value = catalog

        assert loom.discover(source) == catalog
        source.list_targets.assert_called_once_with()
