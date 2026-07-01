# LOOM

**Declarative AI agent framework** — scaffold, configure, and run agents from YAML and a single CLI, built on [Strands Agents](https://github.com/strands-agents/sdk-python).

> **Pre-release (v1.0.0rc1)** — APIs, CLI flags, and on-disk layouts may change without a major version bump. Feedback and issue reports are welcome. Not recommended for production without your own hardening and review.

---

## Why LOOM?

Loom is a **build** library: it turns a declarative YAML definition into a native [Strands](https://github.com/strands-agents/sdk-python) `Agent` / `Graph` / `Swarm` and hands it back. Execution belongs to the caller — Loom does not wrap or manage runtime.

- **Fast scaffolding** — `loom init` and `loom agent new` generate a consistent workspace (`loom.toml`, app config, agent folders).
- **Declarative agents** — Model, prompts, tools, hooks, sessions, retries, and structured output are driven by validated YAML (fail fast at load time via `build_agent` and `loom agent validate`).
- **Native runtime, no wrapper** — `build_agent(name, session) → strands.Agent`. You call, inspect, and compose the real Strands object; Loom is out of the loop after build.
- **Observability** — Each dev/eval invocation appends metrics to `.loom/stats/{agent}.jsonl`; `loom agent stats` summarizes history.
- **Evaluations** — Define cases and evaluators in YAML, run with `loom evals`, persist results under the agent’s `evals/results/`, and check regressions across runs.
- **Multi-agent workflows** — Compose existing agents into a Strands `Graph` or `Swarm` declaratively, via `build_workflow`.
- **Discovery** — `discover()` returns every buildable agent/workflow (name, kind, description) without importing agent code — for a backend that mounts targets dynamically.
- **Environment checks** — `loom doctor` verifies Python, optional AWS/Bedrock access, and project files.

---

## Requirements

- **Python ≥ 3.11** (see [`pyproject.toml`](pyproject.toml))
- **AWS credentials** with access to **Amazon Bedrock** (default model path). Use `loom doctor` to validate.
- Optional: `EDITOR` / `VISUAL` for `loom agent edit`

---

## Installation

The distribution is **`loom-declarative`** (the import package and CLI are still `loom`).
The CLI, evaluation tooling and AWS checks ship as optional extras, so a production
runtime can install just the slim core. Not on PyPI yet — install pinned to a
[release tag](https://github.com/jdbaigorria/loom-dev/tags):

```bash
# Slim runtime — load and run agents in your own app:
pip install "loom-declarative @ git+https://github.com/jdbaigorria/loom-dev@vX.Y.Z"
# Full authoring experience (CLI, wizards, evals, AWS doctor):
pip install "loom-declarative[all] @ git+https://github.com/jdbaigorria/loom-dev@vX.Y.Z"
# or pick extras à la carte: [cli], [evals], [aws]
uv add "loom-declarative[cli] @ git+https://github.com/jdbaigorria/loom-dev@vX.Y.Z"
```

The console script `loom` is available once the `cli` extra is installed.

**Editable install from source (all extras):**

```bash
git clone https://github.com/jdbaigorria/loom-dev
cd loom-dev
uv sync --all-extras
```

---

## Quickstart (CLI)

```bash
# 1. Initialize a project in the current directory
loom init

# 2. Create an agent
loom agent new my_agent

# 3. Edit the system prompt (default: warp/agents/my_agent/config/prompt.md)
#    and adjust warp/agents/my_agent/config/my_agent.yml as needed.

# 4. Run a one-shot message
loom agent run my_agent -m "Hello, what can you do?"

# 5. Or start an interactive REPL-style session
loom agent run my_agent

# 6. Optional: validate config without calling the model
loom agent validate my_agent

# 7. Optional: check your environment
loom doctor
# Skip AWS/Bedrock checks:
loom doctor --no-aws
```

Use `LOOM_ENV` or `loom agent run ... --env <profile>` to pick environment-specific overrides (`warp/config/app.<env>.yml`).

---

## Project layout

Default workspace directory name is **`warp`** (configurable via `loom.toml` → `workspace_name`). Paths below assume that default.

```
project_root/
├── loom.toml                    # Workspace settings (e.g. workspace_name)
├── .loom/                       # Runtime metadata (created as needed)
│   ├── stats/                   # Per-agent invocation metrics (*.jsonl)
│   └── sessions/                # Session storage when configured
└── warp/
    ├── config/
    │   ├── app.yml              # App-level config (region, session, conversation, defaults, …)
    │   ├── app.<env>.yml        # Optional per-environment overrides
    │   └── profiles.toml        # Optional: override/extend built-in model/retry/conversation profiles
    ├── hooks/                   # Optional hook modules
    ├── workflows/               # Multi-agent workflow YAML (loom workflow …)
    │   └── <name>.yml
    ├── entrypoints/             # Entrypoint YAML — router or intent selector (loom entrypoint …)
    │   └── <name>.yml
    └── agents/
        ├── tools/               # Shared tools across agents
        └── <agent_name>/
            ├── config/
            │   ├── <agent_name>.yml   # Agent definition (validated)
            │   └── prompt.md          # Default prompt file (or use inline / folder prompts)
            ├── tools/                 # Agent-specific tools (*.py)
            ├── evals/
            │   ├── evals.yml          # Evaluation experiment (after `loom evals new`)
            │   └── results/           # Reports + history (generated)
            ├── output.py              # Optional: Pydantic schema for structured output
            └── agent.py               # Optional: override — must expose `agent` (see template)
```

---

## CLI reference

| Command | Description |
|--------|-------------|
| `loom init` | Create `loom.toml` and workspace skeleton (`--region`, `--force`, `--interactive`) |
| `loom agent new <name>` | Scaffold a new agent (`--interactive` wizard) |
| `loom agent list` | List agents |
| `loom agent view <name>` | Show resolved agent YAML |
| `loom agent edit <name>` | Open `<name>.yml` in `$EDITOR` / `vi` |
| `loom agent run <name>` | Interactive or `-m` / `--message` one-shot (`--env`) |
| `loom agent dev <name>` | Interactive REPL that hot-reloads config/prompts/tools on edit |
| `loom agent stats <name>` | Aggregate metrics from `.loom/stats/<name>.jsonl` |
| `loom agent validate <name>` | Validate YAML, prompts, tools, output, hooks |
| `loom agent copy <src> <dst>` | Clone an agent directory and fix `name:` in YAML |
| `loom agent remove <name>` | Delete agent (`--force` skips prompt) |
| `loom doctor` | Environment and project checks (`--no-aws` skips AWS/Bedrock) |
| `loom version` | Show `loom`, Python, and key dependency versions |
| `loom evals new <agent>` | Create `warp/agents/<agent>/evals/evals.yml` from template |
| `loom evals run <agent>` | Run evals; optional `--regression` / `--failures` |
| `loom evals compare <agent>` | Show eval history from JSONL |
| `loom evals failures <agent>` | Last run’s failed cases |
| `loom evals regression <agent>` | Compare last two runs (`--threshold`) |
| `loom workflow list` | List workflows under `warp/workflows/` |
| `loom workflow validate <name>` | Validate a workflow YAML without running it |
| `loom workflow run <name>` | Run a workflow interactively or `-m` one-shot (`--env`) |

---

## Programmatic usage

`build_agent(name, session)` resolves the declarative YAML and returns a ready **native `strands.Agent`** — from there you own it: call it, inspect it, or compose it into a Strands `Swarm`/`GraphBuilder`. This is what a production backend uses:

```python
from loom import build_agent, LoomSession

session = LoomSession(session_id="s-001", user_id="u-001")
agent = build_agent("my_agent", session)

result = agent("What is the status?")      # native Strands call
print(result.message["content"][0]["text"])

agent.cleanup()                            # release MCP connections, if any
```

For local development, evals, and the CLI, `loom.dev.run_dev` is a **dev-only** one-shot executor: it builds the target, runs one turn, records `.loom/stats/{name}.jsonl`, and tears it down. Never use it in production — it exists so `loom agent run` and the eval runner don't duplicate this plumbing:

```python
from loom import LoomSession
from loom.dev import run_dev

session = LoomSession(session_id="s-001", user_id="u-001")
run = run_dev("my_agent", "What is the status?", session)

print(run.response.answer)
meta = run.response.metadata
print(meta.total_tokens, meta.response_time_ms, meta.model_id)
```

`run_dev` is **polymorphic over agents and workflows** — it resolves `name` by where its YAML lives (`warp/agents/<name>/` vs `warp/workflows/<name>.yml`) and runs accordingly; pass `kind="agent" | "workflow"` to disambiguate a name that exists as both. More examples (conversation continuity, extras/invocation_state, stats, built-in tools) live under [`examples/`](examples/).

Need the catalog of everything buildable, without importing agent code? Use `discover`:

```python
from loom import discover

for target in discover():
    print(target.name, target.kind, target.description)
```

---

## Multi-agent workflows

Compose existing agents into a **Strands `Graph` (deterministic DAG) or `Swarm` (autonomous hand-offs)** declaratively — no orchestration code. Workflows live in `warp/workflows/<name>.yml`.

**Graph** (ordered nodes + edges):

```yaml
type: graph
name: support
nodes:
  triage:  { agent: triage_agent }
  billing: { agent: billing_agent }
edges:
  - { from: triage, to: billing }     # optional: condition: my_pkg.is_billing
entry_point: triage
```

**Swarm** (agents hand off to each other):

```yaml
type: swarm
name: research
agents: [researcher, writer, editor]
entry_point: researcher
max_handoffs: 20
```

Run it:

```bash
loom workflow validate support
loom workflow run support -m "My invoice looks wrong"
```

Or programmatically — `build_workflow` returns the native Strands `Graph`/`Swarm` plus its built node agents; call the workflow directly, or use `run_dev(..., kind="workflow")` in dev to get the same shaped `AgentResponse` an agent returns (terminal node's text + aggregate token usage):

```python
from loom import build_workflow, LoomSession

session = LoomSession(session_id="s-1", user_id="u-1")
workflow, node_agents = build_workflow("support", session)

result = workflow("My invoice looks wrong")   # native Strands MultiAgentResult
for agent in node_agents:
    agent.cleanup()
```

```python
# Dev-only, same shape as an agent's AgentResponse:
from loom.dev import run_dev

run = run_dev("support", "My invoice looks wrong", session, kind="workflow")
print(run.response.answer, run.response.metadata.total_tokens)
```

Graph/Swarm support is feature-detected against the installed Strands version; on a build that lacks it, `loom workflow run` fails with a clear upgrade hint (`WorkflowConfigError`) instead of crashing.

---

## Routing to the right agent or workflow

Selecting *which* target to run for a given request (deterministic key-based routing, LLM intent classification, etc.) is **execution-time policy that belongs to your backend**, not Loom. Loom's job stops at `discover()` — the catalog of buildable targets (name, kind, description) — and `build_agent` / `build_workflow` to construct whichever one your backend picked:

```python
from loom import discover, build_agent, LoomSession

catalog = {t.name: t for t in discover()}   # [TargetInfo(name, kind, description), ...]
target = catalog["billing_agent"]           # your own routing logic decides this
agent = build_agent(target.name, LoomSession(session_id="s-1", user_id="u-1"))
```

---

## Profiles

Opinionated presets for **models**, **retry** and **conversation**, referenced by name from agent/app YAML. Loom ships built-ins (`model: default | economic | powerful`, `retry: low | medium | high`, `conversation: none | sliding | summarize`); a project overrides or extends them in `warp/config/profiles.toml` (your values are deep-merged over the built-ins):

```toml
# warp/config/profiles.toml
[model.fast]
import_path = "strands.models.bedrock.BedrockModel"
params = { model_id = "anthropic.claude-3-5-haiku-20241022-v1:0" }

[retry.aggressive]
max_attempts = 6
initial_delay = 2
max_delay = 120
```

Then any agent: `model: fast`, `retry: aggressive`. This keeps the opinionated values in config you control rather than baked into the library, and gives one mechanism for "named preset or inline passthrough."

---

## Human-in-the-loop (interrupts)

When a tool pauses execution to ask for human input (a Strands *interrupt*), the response's `interrupts` list is non-empty instead of a final answer. Resume is **native** — feed the answers back to the same live agent as interrupt-response content, no separate `resume()` method:

```python
from loom import build_agent, LoomSession

session = LoomSession(session_id="s", user_id="u")
agent = build_agent("my_agent", session)

result = agent("delete the prod bucket")
while getattr(result, "interrupts", None):
    answers = [
        {"interruptResponse": {"interruptId": it["id"], "response": input(f"{it['name']}: ")}}
        for it in result.interrupts
    ]
    result = agent(answers)             # same live agent, resumes in place
print(result.message["content"][0]["text"])

agent.cleanup()
```

`loom agent run` and `loom agent dev` drive this loop for you: when the agent pauses they prompt in the terminal and resume automatically. The paused agent (and its MCP connections) is kept alive between turns until a normal (non-interrupted) response, or you call `cleanup()`.

---

## Observability

Loom records per-invocation metrics to `.loom/stats/{agent}.jsonl` (see `loom agent stats`). For production tracing, enable the OpenTelemetry that Strands already emits — agent invocations, model calls, and tool executions — by adding a `telemetry` block to `warp/config/app.yml`:

```yaml
telemetry:
  enabled: true
  exporter: otlp        # or: console
  metrics: false
  service_name: my-agents
```

The OTLP endpoint, headers, and protocol come from the standard `OTEL_EXPORTER_OTLP_*` environment variables, so it points at any OTLP collector (Langfuse, Jaeger, Honeycomb, …) with zero code. Setup runs once per process and is feature-detected: on a Strands build without telemetry, it logs a warning and is skipped.

---

## Evaluations

1. Ensure the agent exists and runs: `loom agent run <agent> -m "ping"`.
2. Generate a starter file: `loom evals new <agent>` → edit `warp/agents/<agent>/evals/evals.yml` (cases + evaluators).
3. Run: `loom evals run <agent>` (optionally `--regression` / `--failures`).
4. Inspect history: `loom evals compare <agent>`; standalone regression check: `loom evals regression <agent> --threshold 0.05`.

**Evaluator types** supported in YAML (`type:`) map to Strands evaluators: `output`, `trajectory`, `interactions`, `helpfulness`, `faithfulness`, `goal_success_rate`, `tool_selection`, `tool_parameter`. See [`src/loom/core/loaders/evaluator.py`](src/loom/core/loaders/evaluator.py) for how each type maps and which YAML fields apply.

---

## Agent configuration (overview)

Agent definitions are validated Pydantic models — see [`src/loom/schemas/config/agent.py`](src/loom/schemas/config/agent.py) and related modules under [`schemas/config/`](src/loom/schemas/config/).

- **Models & retry — profiles or inline.** `model:` and `retry:` take either a **profile name** or an **inline config**. Profiles are opinionated presets (see [Profiles](#profiles)); inline is a generic passthrough to any Strands `Model` (Bedrock, OpenAI, Gemini, LiteLLM, Ollama, or a custom subclass). Loom keeps no per-provider schema. See [`src/loom/schemas/config/models.py`](src/loom/schemas/config/models.py).

  Inline models accept a short `provider:` alias (e.g. `provider: openai`) instead of the full dotted `import_path`. Built-in aliases cover all Strands providers; add custom aliases under `[providers]` in `warp/config/profiles.toml`.

  ```yaml
  model: economic          # a profile name
  retry: low

  # …or inline with provider alias (short form):
  model:
    provider: openai
    params:
      model_id: gpt-4o
      client_args: { api_key: ${oc.env:OPENAI_API_KEY} }

  # …or inline with full import_path (escape hatch for custom classes):
  model:
    import_path: strands.models.openai.OpenAIModel
    params:
      model_id: gpt-4o
      client_args: { api_key: ${oc.env:OPENAI_API_KEY} }
  retry: { max_attempts: 6, initial_delay: 2, max_delay: 120 }
  ```

  Built-in `provider` aliases: `bedrock`, `openai`, `openai_responses`, `anthropic`, `gemini`, `litellm`, `ollama`, `mistral`, `llamaapi`, `llamacpp`, `sagemaker`, `writer`.
- **Prompts** — Inline string, file path, or directory (concatenated in order); see `PromptConfig` / [`loaders/prompt.py`](src/loom/core/loaders/prompt.py).
- **Defaults merge** — If `warp/config/app.yml` defines `defaults`, they are merged with each agent YAML (agent wins on conflict) in [`build_agent`](src/loom/core/builder.py).
- **Hooks** — Declared in agent YAML; resolved from built-ins, qualified imports, or `warp/hooks/<name>.py`.
- **Tool execution** — `tool_executor: concurrent | sequential` (optional) selects how multiple tool calls in one turn run. Omit it for the Strands default. Feature-detected: on a Strands build without pluggable executors, loading fails with a clear upgrade hint.
- **MCP servers** — Declare `mcp_servers` in the agent YAML to connect Model Context Protocol servers; their tools are namespaced by the server `name` and made available to the model alongside the agent's own tools. Connections open at build time and close after each invocation. Feature-detected against the installed Strands.

  ```yaml
  mcp_servers:
    - name: filesystem            # tools exposed as filesystem_*
      transport: stdio
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
    - name: github
      transport: http             # or: sse
      url: https://mcp.example.com/github
      headers: { Authorization: "Bearer ${oc.env:GITHUB_TOKEN}" }
  ```
- **Python override** — If `agent.py` is present, it can expose a pre-built `agent` (see [`templates/new/agent.py.j2`](src/loom/templates/new/agent.py.j2)).

---

## Security

LOOM executes arbitrary Python code from your workspace at runtime:

- **Tools** (`warp/agents/<name>/tools/*.py`) are imported and called by the agent.
- **Hooks** (`warp/hooks/*.py`) run before and after each agent invocation.
- **Output classes** (`output:` field) are dynamically imported via `import_path`.
- **Model import paths** (`model.import_path`) load arbitrary provider classes.

> **Do not run workspaces from untrusted sources.** Treat a Loom workspace with the same caution as any executable code.

---

## Limitations and roadmap (honest)

- **Alpha quality** — Expect rough edges, sparse docs outside this file, and evolving APIs.
- **Providers** — Prioritize Bedrock; other providers may not be fully exercised.
- **Prompt sources** — S3, HTTPS, and Bedrock Prompt Management URIs are not first-class yet (validation will flag unsupported prefixes).
- **Multi-agent workflows** — Compose agents declaratively in `warp/workflows/<name>.yml` (`graph` or `swarm`) and run them with `loom workflow run`, or in code via `build_workflow`. See [Multi-agent workflows](#multi-agent-workflows). Conditional graph edges currently take a dotted-path callable (`condition:`); expression strings are not parsed.

---

## Development

```bash
git clone https://github.com/jdbaigorria/loom-dev
cd loom-dev
uv sync --group dev
pre-commit install --hook-type pre-commit --hook-type commit-msg

uv run poe check   # format + lint + type-check
uv run poe test    # run test suite
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

---

## License

This project is licensed under the MIT License — see [`LICENSE`](LICENSE).
