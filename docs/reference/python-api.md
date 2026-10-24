# Python API

Loom is a **build** library: it turns a declarative YAML definition into a native Strands object (`Agent` / `Graph` / `Swarm`) and hands it back. Execution belongs to the caller — Loom does not wrap or manage runtime.

The public, stable surface is importable from the top-level `loom` package:

```python
from loom import (
    build,            # engine: build(agent_config, session, ...) -> strands.Agent
    build_agent,       # by name: build_agent(name, session) -> strands.Agent
    build_workflow,    # by name: build_workflow(name, session) -> (Graph/Swarm, node_agents)
    discover,          # catalog: discover() -> list[TargetInfo]
    TargetInfo,        # a buildable target (name, kind, description)
    LoomSession,       # execution identity (session_id, user_id)
)
from loom_evals import LoomEvals   # evaluation runner — package loom-declarative-evals
from loom.dev import run_dev          # dev-only one-shot executor
from loom.errors import LoomError, AgentNotFoundError, ...   # public exception surface
from loom.ports import ConfigSource    # config-source seam (inject a source)
```

Everything else (`loom.core`, `loom.adapters`, `loom.schemas.config`, loaders, services, CLI internals) is internal and may change without a major version bump.

---

## LoomSession

Execution identity for a build or a `run_dev` call.

```python
from loom import LoomSession

session = LoomSession(session_id="s-001", user_id="u-001")
```

| Field | Type | Description |
|---|---|---|
| `session_id` | `str` | Continues conversation history / session persistence when the same value is reused |
| `user_id` | `str` | User identifier |

---

## build_agent

Build a native `strands.Agent` by name — the shape a production backend uses.

```python
from loom import build_agent, LoomSession

session = LoomSession(session_id="s-1", user_id="u-1")
agent = build_agent("my_agent", session)          # validates config, resolves tools/model/prompt

result = agent("What is the order status?")         # native Strands call
print(result.message["content"][0]["text"])

agent.cleanup()                                     # release MCP connections, if any
```

```python
def build_agent(
    name: str,
    session: LoomSession,
    env: str | None = None,
    *,
    source: ConfigSource | None = None,
    tools: list[str] | None = None,
) -> Agent: ...
```

| Arg | Description |
|---|---|
| `name` | Agent name — resolves its config (and code/asset directory) |
| `session` | Identity for this build |
| `env` | Environment override (e.g. `"prod"`); defaults to `LOOM_ENV` or `"dev"` |
| `source` | Where declarative config comes from. Defaults to the filesystem (`warp/`); inject an alternative to decouple from disk |
| `tools` | Optional subset of the declared tool catalog to activate (by name). `None` activates all declared tools |

Raises `AgentNotFoundError` / `AgentConfigError` / `ToolSelectionError` — see [Exceptions](#exceptions).

**Conversation continuity** is a property of the live agent: build once, call across turns — the agent keeps message history in memory (session persistence is a separate, opt-in concern in `app.yml`). One built agent = one conversation; build a new one per user/conversation.

---

## build

The lower-level engine `build_agent` wraps: takes an already-*resolved* `AgentConfig` (not a name) and assembles the `strands.Agent`. Does no config I/O — use it when you already have validated config (e.g. from a custom `ConfigSource`) or need to inject a runtime `AppConfig` / `WorkspacePaths` directly.

```python
from loom import build

agent = build(agent_config, session, app_config=app_config, tools=None, paths=paths)
```

Most callers want `build_agent`, not `build`, directly.

---

## build_workflow

Build a native Strands `Graph`/`Swarm` (multi-agent workflow) by name. Composes existing agents (each built via `build_agent`) per the workflow YAML in `warp/workflows/<name>.yml`.

```python
from loom import build_workflow, LoomSession

session = LoomSession(session_id="s-1", user_id="u-1")
workflow, node_agents = build_workflow("support", session)

result = workflow("My invoice looks wrong")   # native Strands MultiAgentResult
for agent in node_agents:
    agent.cleanup()                            # release each node's MCP connections
```

`node_agents` is the list of built `strands.Agent` objects backing the workflow's nodes — exposed so you can `cleanup()` them (Graph/Swarm have no `cleanup()` of their own). Raises `WorkflowNotFoundError` / `WorkflowConfigError`.

See [Multi-agent workflows](../guides/workflows.md).

---

## discover

Return the catalog of buildable targets — every agent and workflow a `ConfigSource` knows, without importing agent code.

```python
from loom import discover

for target in discover():
    print(target.name, target.kind, target.description)
```

```python
def discover(source: ConfigSource | None = None) -> list[TargetInfo]: ...
```

### TargetInfo

```python
from loom import TargetInfo

TargetInfo(name: str, kind: Literal["agent", "workflow", "bidi"], description: str = "")
```

Selecting *which* target to run for a given request (routing, intent classification, ...) is execution-time policy for your backend — Loom's job stops at the catalog.

---

## run_dev (dev-only)

`loom.dev.run_dev` builds a target, runs a single turn, records `.loom/stats/<name>.jsonl`, and tears it down. It backs `loom agent run` / `loom agent dev` and the eval runner — **never use it in production**; a backend calls `build_agent`/`build_workflow` and drives the native object itself.

```python
from loom import LoomSession
from loom.dev import run_dev

session = LoomSession(session_id="s-1", user_id="u-1")
run = run_dev("my_agent", "What is the capital of France?", session)

print(run.response.answer)
print(run.response.metadata.total_tokens)
print(run.agent)   # the built strands.Agent (or workflow object) — inspect messages/trajectory
```

```python
def run_dev(
    name: str,
    query: Any,
    session: LoomSession,
    *,
    extras: dict[str, Any] | None = None,
    env: str | None = None,
    kind: Literal["agent", "workflow"] | None = None,
) -> DevRun: ...
```

`run_dev` is **polymorphic over agents and workflows**: it resolves `name` by where its YAML lives (`warp/agents/<name>/` vs `warp/workflows/<name>.yml`) and dispatches accordingly. Pass `kind` to disambiguate a name that exists as both. `extras` is forwarded as native Strands `invocation_state` — tools read it via `tool_context.invocation_state`.

`DevRun` fields: `response` (an `AgentResponse`) and `agent` (the built target).

---

## AgentResponse

The shape `run_dev` returns (workflows are shaped into the same type; a directly-built agent returns the *native* Strands result instead — see [build_agent](#build_agent)).

```python
run.response.answer          # str — final text answer
run.response.metadata        # AgentResponseMetadata
run.response.interrupts      # list[InterruptInfo] — non-empty when the agent paused
run.response.checkpoint      # dict | None — experimental, set when stop_reason is "checkpoint"
```

### AgentResponseMetadata

```python
meta = run.response.metadata

meta.session_id           # str
meta.user_id              # str
meta.total_tokens          # int — input + output
meta.input_tokens          # int
meta.output_tokens         # int
meta.response_time_ms      # float — wall-clock ms
meta.model_id               # str | None — the candidate that answered, after a fallback
meta.model_attempts         # list[dict] — each try: candidate, model_id, outcome
meta.tool_calls             # list[str] — tool names invoked this turn
meta.raw_metrics            # dict | None — Strands' own metrics summary, verbatim
```

`checkpoint` is the marker to send back as `{"checkpointResume": {"checkpoint": response.checkpoint}}`. It does not contain the conversation. `loom agent run` performs that resume until the turn finishes. Pair `checkpointing: true` with `session` in `app.yml` if a process restart must keep history.

### Interrupts (human-in-the-loop)

When a tool pauses execution to ask for human input, `response.interrupts` is non-empty instead of a final answer. Resume is **native** — feed the answers back to the same live agent as interrupt-response content:

```python
result = agent("delete the prod bucket")
while getattr(result, "interrupts", None):
    answers = [
        {"interruptResponse": {"interruptId": it["id"], "response": input(f"{it['name']}: ")}}
        for it in result.interrupts
    ]
    result = agent(answers)          # same live agent, resumes in place
print(result.message["content"][0]["text"])
```

There is no separate `resume()` method — the agent (and its MCP connections) simply needs to stay alive between calls until it stops interrupting.

---

## Plugin contract

`loom-declarative-evals` is a CLI plugin. It depends on this surface of the core, which is public for plugins:

| Symbol | Role |
|---|---|
| `loom.dev.run_dev(name, query, session, *, extras, env, kind) -> DevRun` | Run one case |
| `DevRun.response.answer`, `.metadata.total_tokens`, `.metadata.response_time_ms`, `DevRun.agent` | Output, metrics, trajectory |
| `WorkspacePaths.eval_file` / `eval_dir` / `eval_results_dir` | On-disk layout |
| `loom.schemas.context.LoomSession` | Session per case |
| `loom.utils.loaders.load_config` | Load `evals.yml` |
| `loom.errors.LoomError`, `AgentNotFoundError` | Errors |
| `loom.utils.ui` console helpers | CLI output |
| `loom.adapters.strands.resolve`, `LoomStrandsCompatError` | Vendor ACL |

A plugin advertises a Typer app under the `loom.cli` entry-point group. `loom doctor` lists installed plugins.

## LoomEvals

Ships in `loom-declarative-evals` (`pip install loom-declarative-evals`, or the `[evals]` extra, which is an alias). `from loom import LoomEvals` still works and emits a `DeprecationWarning`.

```python
from loom_evals import LoomEvals

evals = LoomEvals("my_agent")
results = evals.run()

print(results.aggregate_score)
for case in results.cases:
    print(case.name, case.score, case.passed)
```

See [Evaluations](../guides/evals.md).

---

## ConfigSource

The port `build_agent` / `build_workflow` / `discover` use to fetch declarative config, instead of reading YAML off disk directly. The default (`FileConfigSource`) reads the `warp/` workspace folder; implement the `Protocol` to back Loom with a different store (e.g. a document DB) while leaving the engine untouched.

```python
from loom.ports import ConfigSource

class ConfigSource(Protocol):
    def get_agent_config(self, name: str) -> AgentConfig: ...
    def get_app_config(self, env: str | None = None) -> AppConfig: ...
    def get_workflow_config(self, name: str) -> GraphWorkflowConfig | SwarmWorkflowConfig: ...
    def list_targets(self) -> list[TargetInfo]: ...
    def get_target_kind(self, name: str, kind: TargetKind | None = None) -> TargetKind: ...
```

Scope is **declarative only** — a `ConfigSource` never serves code (tool `.py` modules, `output.py`, hooks); code is resolved by import, and in a non-filesystem source, only by dotted path.

---

## Exceptions

```python
from loom.errors import (
    LoomError,                  # base class for everything below
    AgentError,                 # base for agent-related errors
    AgentNotFoundError,         # agent directory or YAML not found
    AgentConfigError,           # YAML schema validation failed
    ModelLoadError,             # model profile unknown or import_path fails
    ToolLoadError,               # tool file not found or invalid
    ToolSelectionError,          # requested tool subset not in the declared catalog
    HookLoadError,                # hook not found or invalid
    OutputLoadError,              # structured-output class not found or invalid
    WorkflowError,                 # base for workflow-related errors
    WorkflowNotFoundError,          # workflow YAML not found
    WorkflowConfigError,             # workflow schema error, or missing Strands capability
    TargetResolutionError,            # discover()/get_target_kind() couldn't resolve a name
)
```

All Loom exceptions carry an optional `.tip` attribute with a human-readable hint for fixing the problem.

---

## Testing helpers

`loom.testing` provides `MockModel` (a fake `strands.Model` that returns predefined text) and `mock_llm`, a context manager that wires it into the build pipeline — no real network calls.

```python
from loom import build_agent, LoomSession
from loom.testing import mock_llm

with mock_llm("Hello!", "How can I help?") as model:
    agent = build_agent("my_agent", LoomSession(session_id="s", user_id="u"))
    result = agent("hi")

assert "Hello" in result.message["content"][0]["text"]
assert model.call_count == 1
```

`MockModel` cycles through the given responses when it runs out of entries; construct it directly for finer control:

```python
from loom.testing import MockModel

model = MockModel(["first", "second"])
```
