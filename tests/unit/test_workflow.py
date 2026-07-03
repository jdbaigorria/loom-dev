"""Tests for declarative multi-agent workflows (schema, builder, public class).

Builder/runtime tests drive **real** Strands Graph/Swarm objects whose nodes are
real Agents backed by the network-free MockModel — no cloud calls — so they
exercise the actual orchestration and result extraction, not a mock of it.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import TypeAdapter, ValidationError

from loom.adapters.config import FileConfigSource
from loom.adapters.strands import Agent
from loom.schemas.config.workflow import (
    GraphEdgeConfig,
    GraphNodeConfig,
    GraphWorkflowConfig,
    SwarmWorkflowConfig,
    WorkflowConfig,
)
from loom.schemas.context import LoomSession
from loom.testing import MockModel

_adapter: TypeAdapter = TypeAdapter(WorkflowConfig)


def _agent(name: str) -> Agent:
    return Agent(
        name=name, model=MockModel([f"{name} output"]), system_prompt="x", callback_handler=None
    )


def _fake_build_agent(agent_name, session, env, *, source=None, model_params=None):
    return _agent(agent_name)


@pytest.fixture
def session() -> LoomSession:
    return LoomSession(session_id="s1", user_id="u1")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class TestWorkflowSchema:
    def test_graph_discriminator_selects_graph_config(self):
        cfg = _adapter.validate_python(
            {
                "type": "graph",
                "name": "support",
                "nodes": {"a": {"agent": "agent_a"}, "b": {"agent": "agent_b"}},
                "edges": [{"from": "a", "to": "b"}],
                "entry_point": "a",
            }
        )
        assert isinstance(cfg, GraphWorkflowConfig)
        assert cfg.edges[0].from_node == "a" and cfg.edges[0].to_node == "b"

    def test_swarm_discriminator_selects_swarm_config(self):
        cfg = _adapter.validate_python({"type": "swarm", "name": "team", "agents": ["r", "w"]})
        assert isinstance(cfg, SwarmWorkflowConfig)
        assert cfg.max_handoffs == 20

    def test_edge_from_to_aliases(self):
        edge = GraphEdgeConfig.model_validate({"from": "x", "to": "y"})
        assert edge.from_node == "x" and edge.to_node == "y"

    def test_graph_edge_referencing_unknown_node_rejected(self):
        with pytest.raises(ValidationError, match="unknown node"):
            GraphWorkflowConfig(
                name="bad",
                nodes={"a": GraphNodeConfig(agent="agent_a")},
                edges=[GraphEdgeConfig.model_validate({"from": "a", "to": "ghost"})],
            )

    def test_graph_entry_point_must_be_a_node(self):
        with pytest.raises(ValidationError, match="entry_point"):
            GraphWorkflowConfig(
                name="bad", nodes={"a": GraphNodeConfig(agent="agent_a")}, entry_point="ghost"
            )

    def test_swarm_entry_point_must_be_an_agent(self):
        with pytest.raises(ValidationError, match="entry_point"):
            SwarmWorkflowConfig(name="bad", agents=["r"], entry_point="ghost")

    def test_graph_requires_at_least_one_node(self):
        with pytest.raises(ValidationError):
            GraphWorkflowConfig(name="empty", nodes={})

    def test_unknown_type_rejected(self):
        with pytest.raises(ValidationError):
            _adapter.validate_python({"type": "mesh", "name": "x"})


# ---------------------------------------------------------------------------
# Builder (real Strands Graph/Swarm)
# ---------------------------------------------------------------------------


class TestWorkflowBuilder:
    def test_build_graph_runs_and_reaches_terminal_node(self, session):
        import loom.core.workflow_builder as wb

        cfg = GraphWorkflowConfig(
            name="support",
            nodes={"triage": GraphNodeConfig(agent="a"), "billing": GraphNodeConfig(agent="b")},
            edges=[GraphEdgeConfig.model_validate({"from": "triage", "to": "billing"})],
            entry_point="triage",
        )
        with patch.object(wb, "build_agent", _fake_build_agent):
            graph, _ = wb._build_graph(cfg, session, "dev", FileConfigSource())
        result = graph("hello")
        assert str(result.status) == "Status.COMPLETED"
        assert set(result.results) == {"triage", "billing"}

    def test_build_swarm_runs(self, session):
        import loom.core.workflow_builder as wb

        cfg = SwarmWorkflowConfig(name="team", agents=["r", "w"], entry_point="r")
        with patch.object(wb, "build_agent", _fake_build_agent):
            swarm, _ = wb._build_swarm(cfg, session, "dev", FileConfigSource())
        result = swarm("hello")
        assert str(result.status) == "Status.COMPLETED"

    def test_graph_missing_strands_primitive_raises(self, session):
        import loom.core.workflow_builder as wb
        from loom.core.exceptions import WorkflowConfigError

        cfg = GraphWorkflowConfig(name="g", nodes={"a": GraphNodeConfig(agent="a")})
        with patch.object(wb.sx, "GraphBuilder", None):
            with pytest.raises(WorkflowConfigError, match="does not provide graph"):
                wb._build_graph(cfg, session, "dev", FileConfigSource())

    def test_injected_source_is_threaded_to_every_node(self, session):
        """build_workflow reads the workflow from the source and threads it to nodes.

        A non-filesystem deployment relies on this: the same ``source`` resolves
        the workflow doc *and* every agent node, so the whole build stays off disk.
        """
        import loom.core.workflow_builder as wb

        cfg = SwarmWorkflowConfig(name="team", agents=["r", "w"], entry_point="r")
        source = MagicMock()
        source.get_workflow_config.return_value = cfg

        seen_sources = []

        def _record(agent_name, sess, env, *, source=None, model_params=None):
            seen_sources.append(source)
            return _agent(agent_name)

        with patch.object(wb, "build_agent", _record):
            wb.build_workflow("team", session, "dev", source=source)

        source.get_workflow_config.assert_called_once_with("team")
        assert seen_sources == [source, source]  # one per node, the injected one

    def test_model_params_are_threaded_to_every_node(self, session):
        """A single per-run overlay reaches every node's build_agent (same run creds)."""
        import loom.core.workflow_builder as wb

        cfg = SwarmWorkflowConfig(name="team", agents=["r", "w"], entry_point="r")
        source = MagicMock()
        source.get_workflow_config.return_value = cfg
        overlay = {"boto_session": object()}

        seen_overlays = []

        def _record(agent_name, sess, env, *, source=None, model_params=None):
            seen_overlays.append(model_params)
            return _agent(agent_name)

        with patch.object(wb, "build_agent", _record):
            wb.build_workflow("team", session, "dev", source=source, model_params=overlay)

        assert seen_overlays == [overlay, overlay]  # one per node, the same overlay


# ---------------------------------------------------------------------------
# Workflow dev run (result mapping via run_dev, kind=workflow)
# ---------------------------------------------------------------------------


class TestWorkflowDevRun:
    def test_run_dev_workflow_returns_answer_and_aggregated_tokens(self, session):
        import loom.core.workflow_builder as wb
        from loom.dev import run_dev

        cfg = GraphWorkflowConfig(
            name="support",
            nodes={"triage": GraphNodeConfig(agent="a"), "billing": GraphNodeConfig(agent="b")},
            edges=[GraphEdgeConfig.model_validate({"from": "triage", "to": "billing"})],
            entry_point="triage",
        )

        with patch.object(wb, "build_agent", _fake_build_agent):
            graph, _ = wb._build_graph(cfg, session, "dev", FileConfigSource())

        with (
            patch("loom.dev.build_workflow", return_value=(graph, [])),
            patch("loom.dev._resolve_kind", return_value="workflow"),
        ):
            run = run_dev("support", "hi", session)

        assert run.response.answer == "b output"  # terminal node text
        assert run.response.metadata.total_tokens > 0
        assert run.response.metadata.raw_metrics["nodes"] == ["triage", "billing"]
