"""Catalog labels: schema validation, TargetInfo immutability, effective-config discovery."""

import pytest
from pydantic import ValidationError

from loom.adapters.config import FileConfigSource
from loom.core.paths import WorkspacePaths
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.workflow import GraphWorkflowConfig, SwarmWorkflowConfig
from loom.schemas.target import TargetInfo


def _agent(**kw) -> AgentConfig:
    return AgentConfig(name="a", **kw)


class TestSchema:
    def test_default_is_empty(self):
        assert _agent().labels == {}

    def test_valid_labels(self):
        cfg = _agent(labels={"areas": ["BILLING", 2, 1.5, True], "acme.expose_metrics": True})
        assert cfg.labels["areas"] == ["BILLING", 2, 1.5, True]
        assert cfg.labels["acme.expose_metrics"] is True

    @pytest.mark.parametrize("key", ["Areas", "1x", "a..b", "a-b", ".a", "a."])
    def test_invalid_key_names_the_key(self, key):
        with pytest.raises(ValidationError) as exc:
            _agent(labels={key: "x"})
        assert key in str(exc.value)

    @pytest.mark.parametrize("value", [{"nested": 1}, [{"a": 1}], None])
    def test_non_flat_value_is_rejected(self, value):
        with pytest.raises(ValidationError, match="areas"):
            _agent(labels={"areas": value})

    def test_misspelled_key_suggests_labels(self):
        with pytest.raises(ValidationError, match="did you mean 'labels'"):
            AgentConfig(name="a", label={"x": 1})

    def test_workflows_accept_labels(self):
        g = GraphWorkflowConfig(name="g", nodes={"n": {"agent": "a"}}, labels={"areas": ["X"]})
        s = SwarmWorkflowConfig(name="s", agents=["a"], labels={"team": "core"})
        assert g.labels == {"areas": ["X"]} and s.labels == {"team": "core"}

    def test_workflow_rejects_bad_key(self):
        with pytest.raises(ValidationError, match="Bad"):
            SwarmWorkflowConfig(name="s", agents=["a"], labels={"Bad": 1})


class TestTargetInfo:
    def test_positional_construction_still_works(self):
        t = TargetInfo("a", "agent", "desc")
        assert t.labels == {}

    def test_hashable_and_labels_ignored_in_hash(self):
        a = TargetInfo("a", "agent", "d", {"areas": ["X"]})
        assert hash(a) == hash(TargetInfo("a", "agent", "d"))

    def test_labels_are_read_only_with_tuple_lists(self):
        t = TargetInfo("a", "agent", labels={"areas": ["X", "Y"]})
        assert t.labels["areas"] == ("X", "Y")
        with pytest.raises(TypeError):
            t.labels["areas"] = ("Z",)  # type: ignore[index]

    def test_source_dict_is_not_aliased(self):
        src = {"areas": ["X"]}
        t = TargetInfo("a", "agent", labels=src)
        src["areas"].append("Y")
        src["new"] = 1
        assert dict(t.labels) == {"areas": ("X",)}


def _ws(tmp_path) -> WorkspacePaths:
    return WorkspacePaths(project_root=tmp_path, workspace_name="warp")


def _write_agent(ws: WorkspacePaths, name: str, body: str = "") -> None:
    cfg = ws.agent(name).yaml_file
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(f"name: {name}\n{body}", encoding="utf-8")


def _write_app(ws: WorkspacePaths, body: str) -> None:
    ws.app_dir.mkdir(parents=True, exist_ok=True)
    (ws.app_dir / "app.yml").write_text(body, encoding="utf-8")


class TestDiscovery:
    def test_reports_agent_and_workflow_labels(self, tmp_path):
        ws = _ws(tmp_path)
        _write_agent(
            ws, "billing", "labels:\n  areas: [BILLING, BACKOFFICE]\n  expose_metrics: true\n"
        )
        ws.workflows_dir.mkdir(parents=True)
        ws.workflow_file("flow").write_text(
            "name: flow\ntype: swarm\nagents: [billing]\nlabels: {areas: [OPS]}\n"
        )
        targets = {t.name: t for t in FileConfigSource(workspace=ws, env="dev").list_targets()}
        assert targets["billing"].labels["areas"] == ("BILLING", "BACKOFFICE")
        assert targets["billing"].labels["expose_metrics"] is True
        assert targets["flow"].labels["areas"] == ("OPS",)

    def test_defaults_labels_merge_and_agent_wins(self, tmp_path):
        ws = _ws(tmp_path)
        _write_app(ws, "defaults:\n  labels:\n    team: x\n    areas: [A, B]\n")
        _write_agent(ws, "plain")
        _write_agent(ws, "override", "labels:\n  team: y\n  areas: [C]\n")
        t = {t.name: t for t in FileConfigSource(workspace=ws, env="dev").list_targets()}
        assert dict(t["plain"].labels) == {"team": "x", "areas": ("A", "B")}
        # dicts merge key by key, lists are replaced
        assert dict(t["override"].labels) == {"team": "y", "areas": ("C",)}

    def test_matches_get_agent_config(self, tmp_path):
        ws = _ws(tmp_path)
        _write_app(ws, "defaults:\n  labels:\n    team: x\n")
        _write_agent(
            ws, "a", "system_prompt: {prompt: hi, is_resolved: true}\nlabels:\n  areas: [Z]\n"
        )
        src = FileConfigSource(workspace=ws, env="dev")
        (target,) = src.list_targets()
        cfg = src.get_agent_config("a")
        assert {
            k: v if not isinstance(v, tuple) else list(v) for k, v in target.labels.items()
        } == cfg.labels

    def test_invalid_agent_does_not_break_discovery(self, tmp_path):
        ws = _ws(tmp_path)
        _write_agent(ws, "good", "labels: {areas: [X]}\n")
        _write_agent(ws, "bad", "labels: {Bad: 1}\n")
        t = {t.name: t for t in FileConfigSource(workspace=ws, env="dev").list_targets()}
        assert t["bad"].kind == "agent" and t["bad"].description == ""
        assert dict(t["bad"].labels) == {}
        assert t["good"].labels["areas"] == ("X",)

    @pytest.mark.parametrize("with_defaults", [False, True])
    def test_each_agent_yaml_is_read_once(self, tmp_path, monkeypatch, with_defaults):
        ws = _ws(tmp_path)
        if with_defaults:
            _write_app(ws, "defaults:\n  labels: {team: x}\n")
        _write_agent(ws, "a", "description: one-read\n")
        _write_agent(ws, "b")
        agent_yamls = {str(ws.agent(n).yaml_file) for n in "ab"}
        reads: list[str] = []

        import loom.adapters.config.file_source as fs
        import loom.core.loaders.agent as agent_loader

        for mod in (fs, agent_loader):
            real = mod.load_config

            def counting(path, _real=real):
                if str(path) in agent_yamls:
                    reads.append(str(path))
                return _real(path)

            monkeypatch.setattr(mod, "load_config", counting)
        agent_loader.get_agent_config.cache_clear()

        FileConfigSource(workspace=ws, env="dev").list_targets()
        assert sorted(reads) == sorted(agent_yamls)


def test_build_is_unaffected_by_labels(monkeypatch):
    from loom.core.builder import build
    from loom.schemas.config.app import AppConfig
    from loom.schemas.context import LoomSession
    from loom.testing import MockModel

    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))
    base = {
        "name": "a",
        "system_prompt": {"prompt": "hi", "is_resolved": True},
        "conversation": "none",
    }

    def go(**extra):
        return build(
            AgentConfig(**base, **extra),
            LoomSession(session_id="s", user_id="u"),
            app_config=AppConfig(conversation="none"),
        )

    plain, labelled = go(), go(labels={"areas": ["X"]})
    assert plain.system_prompt == labelled.system_prompt
    assert plain.trace_attributes == labelled.trace_attributes
    assert not hasattr(labelled, "labels")
