# Multi-agent workflows

Compose existing agents into a **deterministic DAG (Graph)** or an **autonomous hand-off network (Swarm)** — declaratively, from a YAML file. No orchestration code needed.

Workflows live in `warp/workflows/<name>.yml`.

## Graph (deterministic DAG)

A **Graph** defines a fixed set of nodes (agents) and edges (connections). Execution follows the declared edges from the entry point.

```yaml title="warp/workflows/support.yml"
type: graph
name: support
nodes:
  triage:  { agent: triage_agent }
  billing: { agent: billing_agent }
  tech:    { agent: tech_agent }
edges:
  - { from: triage, to: billing }
  - { from: triage, to: tech }
entry_point: triage
max_node_executions: 50   # optional; stops a cyclic graph
execution_timeout: 120    # optional, seconds for the whole graph
node_timeout: 30          # optional, seconds for one node
reset_on_revisit: false   # optional; reset a node's state when it runs again
```

Leave `max_node_executions` and `execution_timeout` unset and Strands warns that graph execution is unbounded. Set either one to silence that warning. `node_timeout` and `reset_on_revisit` are independent of it.

### Conditional edges

Add a `condition:` dotted-path callable that returns a truthy value to decide if the edge is followed:

```yaml
edges:
  - { from: triage, to: billing, condition: my_pkg.routing.is_billing_issue }
  - { from: triage, to: tech,    condition: my_pkg.routing.is_tech_issue }
```

```python title="my_pkg/routing.py"
def is_billing_issue(response) -> bool:
    return "billing" in response.answer.lower()

def is_tech_issue(response) -> bool:
    return "technical" in response.answer.lower() or "error" in response.answer.lower()
```

## Swarm (autonomous hand-offs)

A **Swarm** lets agents hand off to each other. Any agent in the swarm can transfer to any other — the agents decide, not the YAML:

```yaml title="warp/workflows/research.yml"
type: swarm
name: research
agents: [researcher, writer, editor]
entry_point: researcher
max_handoffs: 20       # prevents infinite loops
```

## CLI

```bash
loom workflow list                         # list workflows in warp/workflows/
loom workflow validate support             # validate YAML + check agents exist
loom workflow run support                  # interactive REPL
loom workflow run support -m "My invoice looks wrong"  # one-shot
```

## Python API

`build_workflow(name, session)` resolves the YAML and returns the native Strands `Graph`/`Swarm` plus the list of built node agents — call it directly:

```python
from loom import build_workflow, LoomSession

session = LoomSession(session_id="s-1", user_id="u-1")
workflow, node_agents = build_workflow("support", session)

result = workflow("My invoice looks wrong")   # native Strands MultiAgentResult
for agent in node_agents:
    agent.cleanup()                            # release each node's MCP connections
```

### Dev-only one-shot

`loom.dev.run_dev` runs a workflow exactly like an agent and shapes the result into the same `AgentResponse` an agent returns — the terminal node's answer plus the workflow's **aggregate** token usage. It resolves `name` to `warp/workflows/<name>.yml` and dispatches automatically:

```python
from loom import LoomSession
from loom.dev import run_dev

session = LoomSession(session_id="s-1", user_id="u-1")
run = run_dev("support", "My invoice looks wrong", session)
print(run.response.answer)
print(run.response.metadata.total_tokens)  # sum of all nodes
```

If a name exists as both an agent and a workflow, disambiguate with `kind`:

```python
run = run_dev("support", "My invoice looks wrong", session, kind="workflow")
```

This is dev-only (see [Running an agent](agents.md#running-an-agent-python)) — it always tears the workflow's node agents down after one run. Use `build_workflow` directly for a reusable handle, async iteration over Strands' own streaming API, or custom composition.

## Validation

`loom workflow validate` checks:

- YAML schema is valid
- All referenced agents exist in `warp/agents/`
- Edge targets resolve to declared nodes

```bash
loom workflow validate research
# ✅ YAML schema valid
# ✅ agent 'researcher' found
# ✅ agent 'writer' found
# ✅ agent 'editor' found
# ✅ Workflow 'research' is valid (type=swarm, 3 agent(s)).
```

## Availability

Graph and Swarm support is feature-detected against the installed Strands version. On a Strands build without them, `loom workflow run` fails with a `WorkflowConfigError` and a clear upgrade hint instead of crashing:

```
WorkflowConfigError: The installed Strands version does not provide graph orchestration.
  tip: Upgrade strands-agents to a version that ships strands.multiagent.GraphBuilder.
```
