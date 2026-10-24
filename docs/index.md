# Loom

**Declarative AI agent framework** — scaffold, configure, and run agents from YAML and a single CLI, built on [Strands Agents](https://github.com/strands-agents/harness-sdk).

> **Pre-release (v1.0.0rc1)** — APIs, CLI flags, and on-disk layouts may change without a major version bump. Feedback and issue reports are welcome.

---

## Why Loom?

Strands Agents is a capable runtime for building AI agents in Python. Loom sits on top of it as a **build** library — it turns a declarative YAML definition into a native Strands object and hands it back, adding the authoring layer that Strands deliberately leaves out:

| What Strands gives you | What Loom adds |
|---|---|
| Agent runtime | Declarative YAML config (validated at load time) |
| Model providers | Profile system + short `provider:` aliases |
| Tools via decorator | Automatic tool loading from files/directories |
| Python API | `build_agent(name, session) → strands.Agent` — no wrapper, native object back |
| — | CLI: `loom init`, `loom agent new`, `loom agent run`, ... |
| — | Hot-reload dev loop (`loom agent dev`) |
| — | Multi-agent workflows (Graph / Swarm) via `build_workflow` |
| — | Catalog discovery (`discover()`) — every buildable target, without importing code |
| — | Built-in eval framework with YAML test cases |
| — | Per-invocation metrics + OpenTelemetry export |

## Core features at a glance

### Fast scaffolding

```bash
loom init                     # creates loom.toml + warp/ workspace
loom agent new my_agent       # scaffolds a new agent directory
loom agent dev my_agent       # hot-reload REPL — edit and iterate without restart
```

### Declarative agents

Everything that drives an agent — model, prompts, tools, hooks, sessions, retries, MCP servers, structured output, and the Strands 1.62 fields (plugins, context, memory, interventions, sandbox, storage) — lives in YAML that Loom validates at load time. A field left out stays off. Bad config fails immediately, not mid-invocation.

```yaml title="warp/agents/my_agent/config/my_agent.yml"
name: my_agent
description: "Customer support assistant"
model: economic          # built-in profile → Claude Haiku 5.5 on Bedrock
retry: low
system_prompt: prompt.md
tools:
  - search_orders
  - shared.knowledge_base
```

### Native Strands object back

```python
from loom import build_agent, LoomSession

session = LoomSession(session_id="s-001", user_id="u-001")
agent = build_agent("my_agent", session)          # → strands.Agent

result = agent("Where is my order?")               # native Strands call
print(result.message["content"][0]["text"])
agent.cleanup()
```

For local development, `loom.dev.run_dev` builds, runs one turn, and records stats/metadata in one call — see [Quickstart](quickstart.md).

---

## Installation

Not on PyPI yet — install pinned to a [release tag](https://github.com/jdbaigorria/loom-dev/tags):

=== "Full (CLI + evals + AWS)"
    ```bash
    pip install "loom-declarative[all] @ git+https://github.com/jdbaigorria/loom-dev@vX.Y.Z"
    ```

=== "Slim runtime only"
    ```bash
    pip install "loom-declarative @ git+https://github.com/jdbaigorria/loom-dev@vX.Y.Z"
    ```

=== "Pick extras"
    ```bash
    pip install "loom-declarative[cli] @ git+https://github.com/jdbaigorria/loom-dev@vX.Y.Z"    # CLI + wizards
    pip install "loom-declarative[evals] @ git+https://github.com/jdbaigorria/loom-dev@vX.Y.Z"   # alias of loom-declarative-evals
    pip install "loom-declarative[aws] @ git+https://github.com/jdbaigorria/loom-dev@vX.Y.Z"     # AWS/Bedrock checks
    pip install "loom-declarative[cedar] @ git+https://github.com/jdbaigorria/loom-dev@vX.Y.Z"   # Cedar interventions
    ```

See [Installation](installation.md) for detailed setup including editable installs and source builds.

---

## Next steps

<div class="grid cards" markdown>

-   :material-clock-fast:{ .lg .middle } **[Quickstart](quickstart.md)**

    Build your first agent in 5 minutes.

-   :material-file-code:{ .lg .middle } **[Creating agents](guides/agents.md)**

    Agent YAML schema, tools, hooks, prompts, structured output.

-   :material-shield-account:{ .lg .middle } **[Memory, context, and control](guides/memory-context-control.md)**

    Plugins, context, memory, interventions, sandbox, and experimental checkpoints.

-   :material-tournament:{ .lg .middle } **[Workflows](guides/workflows.md)**

    Compose agents into deterministic DAGs or autonomous swarms.

</div>
