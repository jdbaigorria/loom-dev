"""Schema for a declarative multi-agent workflow YAML.

A workflow composes existing Loom agents into one of two Strands multi-agent
primitives, selected by the ``type`` discriminator:

- ``graph`` — deterministic DAG. Nodes wrap agents; edges define execution order
  and may carry an optional ``condition`` (a dotted path to a
  ``Callable[[GraphState], bool]``) for conditional routing.
- ``swarm`` — a self-organizing team of agents that hand off autonomously.

Example (``warp/workflows/support.yml``)::

    type: graph
    name: support
    nodes:
      triage:  { agent: triage_agent }
      billing: { agent: billing_agent }
    edges:
      - { from: triage, to: billing }
    entry_point: triage
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GraphNodeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent: str = Field(description="Name of an existing Loom agent to run at this node")


class GraphEdgeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    condition: str | None = Field(
        default=None,
        description="Optional dotted path to a Callable[[GraphState], bool] gating this edge",
    )


class _WorkflowBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str = "Workflow created by Loom"


class GraphWorkflowConfig(_WorkflowBase):
    type: Literal["graph"] = "graph"
    nodes: dict[str, GraphNodeConfig] = Field(min_length=1)
    edges: list[GraphEdgeConfig] = Field(default_factory=list)
    entry_point: str | None = None

    @model_validator(mode="after")
    def _check_references(self) -> GraphWorkflowConfig:
        ids = set(self.nodes)
        for edge in self.edges:
            if edge.from_node not in ids:
                raise ValueError(f"Edge 'from' references unknown node '{edge.from_node}'")
            if edge.to_node not in ids:
                raise ValueError(f"Edge 'to' references unknown node '{edge.to_node}'")
        if self.entry_point is not None and self.entry_point not in ids:
            raise ValueError(f"entry_point '{self.entry_point}' is not a declared node")
        return self


class SwarmWorkflowConfig(_WorkflowBase):
    type: Literal["swarm"] = "swarm"
    agents: list[str] = Field(min_length=1, description="Agent names participating in the swarm")
    entry_point: str | None = None
    max_handoffs: int = Field(default=20, ge=1)
    max_iterations: int = Field(default=20, ge=1)

    @model_validator(mode="after")
    def _check_entry_point(self) -> SwarmWorkflowConfig:
        if self.entry_point is not None and self.entry_point not in self.agents:
            raise ValueError(f"entry_point '{self.entry_point}' is not in agents")
        return self


WorkflowConfig = Annotated[
    GraphWorkflowConfig | SwarmWorkflowConfig,
    Field(discriminator="type"),
]
