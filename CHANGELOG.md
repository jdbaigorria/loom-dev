# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`loom-declarative-evals` package.** The evaluation runner, `loom evals` CLI, and
  `strands_evals` adapter moved out of the core into this package (import `loom_evals`).
  `pip install "loom-declarative[evals]"` remains as an alias. `from loom import LoomEvals`
  still works and emits a `DeprecationWarning`; use `from loom_evals import LoomEvals`.
  CLI plugins advertise a Typer app under the `loom.cli` entry-point group. A plugin that
  fails to load is still mounted and reports the error. `loom doctor` lists installed plugins.

### Changed

- **Breaking: unknown config keys are rejected.** Agent, app, conversation, session,
  retry, prompt, hook, and tool models use `extra="forbid"`. A typo such as `toolz`
  fails at load time and suggests the closest field. `version` is now a real field
  on agent YAML (the `loom agent new` template already writes it).
- **Per-agent `conversation` is honored.** An agent YAML `conversation` overrides
  `app.yml`. `kind: bidi` rejects `conversation`.

- **`region` removed from `loom.toml`; it lives only in `app.yml` now.** `loom.toml`
  is project layout/bootstrap (the workspace locator); `region` is a runtime/infra
  setting and belongs with the rest of the runtime config in `app.yml`. The
  `loom.toml` copy was dead (written by `loom init`, read by nothing). A legacy
  `region` in `loom.toml` is ignored with a deprecation warning, so existing
  projects keep working. **Migration:** remove `region` from `loom.toml` (set it in
  `app.yml` if not already there).

- **Session persistence is now off by default (was file-backed).** `AppConfig.session`
  defaults to `None`: a factory should not silently write conversation state to disk,
  and two persistences (Loom + a harness) are the poisoned-session bug. Enable it
  explicitly with a `session:` block in `app.yml`; `loom init` scaffolds a commented
  example showing how. **Migration:** if you relied on automatic file sessions, add a
  `session:` block to `app.yml`.

- **`profiles.toml` moved to `warp/config/profiles.toml`.** Previously it lived at
  `warp/profiles.toml` alongside hooks/, workflows/, and agents/. It now lives in
  `warp/config/` alongside `app.yml`, which is the natural home for all project
  configuration. `loom init` scaffolds it in the new location.

- **Distribution renamed `loom` → `loom-declarative`.** The import package and the
  `loom` CLI command are unchanged; only the PyPI/distribution name changes
  (`pip install loom-declarative`). More descriptive and avoids a name clash.
- **Modular install via extras.** The runtime core (`pip install loom-declarative`)
  now depends only on `strands-agents` + `omegaconf`. The CLI, evaluation tooling
  and AWS checks moved to optional extras: `[cli]`, `[evals]`, `[aws]`, and `[all]`.
  `import loom` no longer pulls in `strands_evals` (lazy `LoomEvals`), and `loom evals`
  registers only when the `evals` extra is installed.
- **Default workspace directory renamed `weave` → `warp`.** Still fully configurable
  via `loom.toml` (`workspace_name`); existing projects are unaffected because they
  pin the name in `loom.toml`. Only the value `loom init` scaffolds by default changes.

### Added

- **`builtin.apicall` domain mode: `omit_if_default` per-param flag.** When a param
  carries `omit_if_default: true` and the model leaves it at its `default`, its key is
  dropped from the request (`body`/`query`/`headers`) instead of being sent with the
  default value — mirroring a hand-written tool that builds the payload conditionally
  (`if nro_doc: payload["nroDoc"] = nro_doc`). Avoids sending `0`/`""` that a backend
  might treat as a real filter rather than an absent field. Requires a `default` and is
  rejected on path params (validated at build time). Found migrating a real
  hand-written list endpoint.
- **Stateless functional API: `loom.invoke` and `loom.build`.** `invoke(name, request)`
  is a one-shot — build the target, run the query once, always tear down MCP, return —
  for the common serverless/Lambda case with no multi-turn continuation. It is
  **polymorphic over agents and workflows**: it resolves `name` by where its YAML lives
  (`warp/agents/{name}/` vs `warp/workflows/{name}.yml`) and dispatches accordingly, so a
  swarm/graph runs through the same call as a plain agent (`kind="agent"|"workflow"`
  disambiguates a name that exists as both). `build(name, request)` returns the
  `strands.Agent` without executing (agent-only). Unlike the `LoomAgent` class, `invoke`
  never keeps the target alive, so it closes MCP connections even when an agent pauses on
  an interrupt (no leak) — at the cost of not supporting `resume`. New `LoomAgent.close()`
  tears down a paused agent explicitly. Shared internals extracted to
  `loom.core.response.run_and_record` (execution core) and `loom.core.target.resolve_target_kind`
  (agent-vs-workflow resolution, now also used by entrypoint dispatch). `run()` is a
  deprecated alias of `invoke`.

- **Built-in tools (`builtin.kb`, `builtin.apicall`).** Two ready-made tools shipped
  with Loom, attached from YAML with the `builtin.` prefix — no Python file required.
  `builtin.kb` searches one or more Amazon Bedrock Knowledge Bases (multi-KB fan-out +
  score-ranked merge, optional `kb_id` targeting); `builtin.apicall` is a generic HTTP
  tool with a mandatory path allow-list (SSRF guard) and a per-instance `name`, so
  several endpoints can coexist on one agent without a tool-name collision. Both return
  a Strands `ToolResult`. `ToolConfig` gains a `source` field (`file`/`shared`/`builtin`);
  resolution lives in `loom.builtins.BUILTIN_TOOLS`. Needs the `aws` extra (kb) and the
  new `tools` extra (apicall, `requests`). See `examples/08_builtins`.

- **Declarative entrypoints.** New `LoomEntrypoint` class and `loom entrypoint list|validate|run`
  CLI group. An entrypoint (`warp/entrypoints/<name>.yml`) is a selector layer that
  picks exactly one target (an agent or a workflow) and delegates the full request to it.
  Two strategies: `type: router` (deterministic — resolves a dot-path from
  `AgentRequest.extras` and maps the value to a target name via a table, no LLM) and
  `type: intent` (LLM classifier — a small model reads the query and picks the best target
  from `candidates`, guided by their own `description` fields). The returned `AgentResponse`
  is the real response of the chosen target; token counts and latency reflect the target
  agent/workflow, not a synthetic wrapper. `loom entrypoint validate` checks schema + verifies
  all targets exist as agents or workflows. `loom init` now scaffolds a `warp/entrypoints/`
  directory with a commented example.

- **Inline model `provider` alias.** An inline model can name its class with a short
  `provider:` alias (e.g. `provider: openai`) instead of the full dotted `import_path`.
  Aliases are data (`BUILTIN_PROVIDERS`) extensible via `[providers]` in
  `warp/profiles.toml`; `import_path` remains the escape hatch for custom classes.
  Built-in aliases: `bedrock`, `openai`, `openai_responses`, `anthropic`, `gemini`,
  `litellm`, `ollama`, `mistral`, `llamaapi`, `llamacpp`, `sagemaker`, `writer`.

- **Profiles layer.** Opinionated presets for models, retry and conversation,
  referenced by name from agent/app YAML (`model: economic`, `retry: low`,
  `conversation: summarize`). Built-ins ship in code
  (`model: default|economic|powerful`, `retry: low|medium|high`,
  `conversation: none|sliding|summarize`) and a project overrides/extends them in
  `weave/profiles.toml` (deep-merged). Replaces the hardcoded `retry.PROFILES` dict,
  the typed-Bedrock default and the conversation/summarizer hardcodes — opinions now
  live in config, not in library Python. The summarizer's model defaults to the
  `economic` profile. `loom init` scaffolds a commented `profiles.toml`. Built-in
  scalar defaults (AWS region, session path) are centralized in `loom.config.defaults`.
- **`loom.run(name, request)`** — one-shot convenience for the common
  stateless/serverless case (equivalent to `LoomAgent(name).invoke(request)`).
  Use the `LoomAgent` class when you need a long-lived handle (conversation
  continuity, `resume`, `as_tool`).
- **Human-in-the-loop interrupts.** When a tool pauses for human input,
  `LoomAgent.invoke` now surfaces the pending interrupts on
  `AgentResponse.interrupts` (new field) instead of a final answer, and
  `LoomAgent.resume(request, {id: answer})` continues from the paused state. The
  agent (and any MCP connections) is kept alive between invoke and resume.
  `loom agent run` / `loom agent dev` drive the prompt-and-resume loop in the
  terminal automatically.
- **Hot-reloading dev loop.** `loom agent dev <name>` runs an interactive REPL
  that fingerprints the agent's config, prompts, and tools by mtime and rebuilds
  the agent before the next message when anything changed — edit and iterate
  without restarting. A reload that fails validation keeps the previous working
  agent. Backed by `clear_config_caches()`; tool code reloads for free since
  tools are re-executed (not cached in `sys.modules`).
- **Declarative MCP servers.** New optional agent field `mcp_servers` connects
  Model Context Protocol servers (stdio for local processes, http/sse for remote);
  their tools are namespaced by the server `name` and exposed to the model
  alongside the agent's own tools. Connections open at build time and are torn
  down after each `LoomAgent.invoke`. Feature-detected via the ACL `capabilities`
  module. Verified end-to-end against a real stdio MCP server.
- **Declarative OpenTelemetry export.** New optional `telemetry` block in
  `app.yml` (`enabled`, `exporter: otlp|console`, `metrics`, `service_name`) wires
  up an exporter for the traces/metrics Strands already emits, with zero user
  code. OTLP endpoint/headers come from the standard `OTEL_EXPORTER_OTLP_*` env
  vars. Setup is idempotent (once per process), feature-detected (skipped with a
  warning on a Strands build without telemetry), and scaffolded as a commented
  example by `loom init`.
- **Declarative tool execution strategy.** New optional agent field
  `tool_executor: concurrent | sequential` selects how multiple tool calls in one
  turn run (omit for the Strands default). Feature-detected via the ACL
  `capabilities` module — on a Strands build without pluggable executors, loading
  fails with a clear upgrade hint instead of an import error.
- **Declarative multi-agent workflows.** Compose existing agents into a Strands
  `Graph` (deterministic DAG) or `Swarm` (autonomous hand-offs) from
  `weave/workflows/<name>.yml` — no orchestration code. New public class
  `LoomWorkflow` (returns the same `AgentResponse` as `LoomAgent`, with the
  terminal node's text and aggregate token usage) and CLI group
  `loom workflow list|validate|run`. Graph/Swarm availability is feature-detected
  via the ACL `capabilities` module, so a Strands build without them fails with a
  clear upgrade hint instead of crashing. Graph edges support an optional
  dotted-path `condition` callable. `loom init` now scaffolds `weave/workflows/`.
- **Nightly Strands compatibility CI** (`.github/workflows/strands-compat.yml`):
  runs the suite against both the newest Strands on PyPI (canary for the next
  breaking release) and the lowest declared versions (floor guard), and opens a
  `strands-compat` issue on failure. Validated locally: the suite passes
  unchanged from strands-agents 1.34.0 through 1.42.0 — the ACL absorbed 8 minor
  releases with no code change.
- **AgentResult contract tests** (`tests/unit/test_strands_contract.py`): assert
  the real result shape Loom reads (`message.content[].text`, `stop_reason`,
  `metrics.get_summary()` usage/duration/tool_usage) using a real Agent driven by
  the network-free `MockModel`, so an upstream shape change fails loudly instead
  of silently regressing metrics.
- CI test matrix widened to Python 3.11–3.14.
- **Strands anti-corruption layer (ACL)** under `loom.adapters.strands`: every
  `strands` / `strands_evals` import in Loom now resolves through a single layer
  with version-tolerant fallback paths (`resolve()`), a feature-detection module
  (`capabilities.py`), and an actionable `LoomStrandsCompatError`. A breaking
  Strands release is now a one-file fix instead of a codebase-wide hunt.
- Ruff `banned-api` rule (TID251) enforcing that `strands` / `strands_evals` are
  imported only from the ACL (examples and the ACL itself are exempt).
- Surface tests (`tests/unit/test_adapters_strands.py`) that verify every ACL
  symbol resolves against the installed Strands, catching upstream module moves
  without an LLM call.
- Documented public API stability boundary in `loom/__init__.py`: only the
  top-level re-exports (`LoomAgent`, `LoomEvals`, `AgentRequest`, `AgentResponse`,
  `LoomContext`, `LoomSession`) are public; everything else is internal.

### Changed

- **Stats format.** `.loom/stats/{agent}.jsonl` now persists Strands' own metrics
  summary verbatim under `metrics` plus session context, instead of re-derived flat
  fields. `loom agent stats` reads from the summary and still understands older
  records. Wizard autocomplete data (model ids, AWS regions) moved to a data module.
- **Breaking — model & retry config.** `model:` and `retry:` are now either a
  **profile name** (resolved from the profiles layer) or an **inline config**.
  Removed the typed `BedrockModelConfig`/`BedrockModelProvider`, the
  `provider:`/`config:` model wrapper, and the `RetryStrategy` profile wrapper.

  ```yaml
  model: economic                 # profile name …
  retry: low
  model:                          # … or inline passthrough
    import_path: strands.models.openai.OpenAIModel
    params: { model_id: gpt-4o }
  retry: { max_attempts: 6, initial_delay: 2, max_delay: 120 }
  ```

  Migration: `model: { provider: bedrock, config: { model_id: X } }` →
  `model: { import_path: strands.models.bedrock.BedrockModel, params: { model_id: X } }`
  or a profile; `retry: { profile: low }` → `retry: low`.
- **Breaking — Bedrock inference defaults:** `temperature`, `max_tokens` and
  `stop_sequences` now default to unset (were `0.0`, `1024`, `["END"]`). Loom no
  longer imposes opinionated inference values; unset fields fall through to
  Strands/Bedrock defaults. In particular the hardcoded `stop_sequences=["END"]`
  (which silently truncated output) is gone. Set them explicitly if you need them.
- **Lowered `requires-python` from `>=3.14` to `>=3.11`** (verified: full suite
  passes on 3.11–3.14) to widen adoption.
- Strands dependency moved from an exact-ish pin (`strands-agents>=1.34.1`) to a
  compatible range (`strands-agents>=1.34,<2.0`, `strands-agents-evals>=0.1.13,<0.2`),
  letting patch/minor releases in.

### Fixed

- **`loom agent validate` reported builtin/import tools as "not found".** The
  tool check always looked for a `{name}.py` on disk, ignoring `tool.source`, so a
  `builtin.kb` / `builtin.apicall` (or a dotted `module:fn` import) was flagged as
  a missing file on an agent that builds and runs fine — a false negative in the
  very "validate without calling the model" flow it exists for. Builtins now
  validate against `BUILTIN_TOOLS`; import tools resolve the symbol in a dry-run
  (no instantiation); file/shared tools are unchanged. Found migrating a real
  agent (KB + 3 `apicall` builtins).
- `ProjectService.run_doctor` used unparenthesized `except A, B:` which on
  Python <3.14 is a `SyntaxError` and on 3.14 silently failed to catch the second
  exception type; now `except (A, B):`.
- `schemas.config.evals` raised `NameError` on Python <3.14 from a self-referencing
  return annotation; added `from __future__ import annotations`.
- `loom init` scaffolded a `hook/` directory while the loader reads `hooks/`, so
  hooks dropped into a fresh workspace were never found. It now scaffolds `hooks/`.
- `loom agent new` emitted `output: None` into the generated YAML (a stray string),
  so a freshly scaffolded agent failed to run with `OutputLoadError: Class 'None'
  not found`. The `output` line is now omitted unless an output schema is set.
- `loom agent list` broke after the profiles refactor (it read the old
  `model.provider` shape and rendered "Error" for a normal `model: default` agent);
  it now shows a model descriptor (profile name or inline id) and the table columns
  are aligned. Dropped the dead `AgentSummary.provider` field.
- **`builtin.apicall`'s `bind.select` dropped the whole response when a path
  crossed a list.** `_project` only navigated dicts; against the common pagination
  shape (`{"body": [...]}`) a path like `body.codigo` resolved nothing and the
  projection returned `{}` — silently blanking the response instead of filtering
  it. `select` now maps the projection over every item of a list it traverses (at
  any depth, including a list at the root), and a path entry may rename its leaf
  with a `"src:dst"` suffix (e.g. `"body.codigo:body.id"`); both sides of `:` must
  share the same nesting depth. Found migrating a real agent whose
  list-returning endpoints had to skip `select` entirely to avoid this.

### Removed

- Dead `callback_handler` field on the agent config schema (it was always ignored
  — `build_agent` hardcodes `callback_handler=None`).
- Obsolete empty `router/` package and its workspace scaffold, superseded by
  `workflows/`, and the unused `loom.utils.visualizations` module.

## [0.4.0] - 2026-04-06

### Changed

- **Breaking:** Path layout is no longer exposed as a mutable `LoomPaths` singleton (`paths`). Use `build_workspace_paths(project_root=..., config=...)` to obtain a frozen `WorkspacePaths` (with nested `MetadataPaths` / `AgentPaths` where applicable). Package assets (init/agent/evals templates) are module-level constants (`INIT_TEMPLATES`, `AGENT_TEMPLATES`, `EVALS_TEMPLATES`, …). Existence checks for agent YAML are centralized in `resolve_existing_agent_yaml(ws, name)`.

### Migration

| Before | After |
|--------|-------|
| `from loom.core.paths import paths` | `from loom.core.paths import build_workspace_paths` — then `ws = build_workspace_paths()` |
| `paths.root` | `ws.project_root` or `ws.root` |
| `paths.resolve_agent_yaml(name)` | `resolve_existing_agent_yaml(build_workspace_paths(), name)` or `ws.resolve_agent_yaml(name)` |
| `from loom.core.paths import LoomPaths` | Construct `WorkspacePaths(project_root, workspace_name)` or call `build_workspace_paths()` |

## [0.3.0] - 2026-04-06

### Changed

- **Breaking:** Declarative configuration schemas moved under `loom.schemas.config` (e.g. `AgentConfig`, `AppConfig`, `LoomConfig`). The `loom.schemas` package root now reexports only **request**, **response**, and **context** types (`AgentRequest`, `AgentResponse`, `LoomContext`, `LoomSession`, and related request/response helpers). No compatibility shims for old import paths.
- **Added:** `LoomContext` and `LoomSession` are exported from the top-level `loom` package alongside `AgentRequest` and `AgentResponse`.

### Migration

| Before | After |
|--------|-------|
| `from loom.schemas import AgentConfig` | `from loom.schemas.config.agent import AgentConfig` |
| `loom.schemas.agent` | `loom.schemas.config.agent` |
| `loom.schemas.app` | `loom.schemas.config.app` |
| `loom.schemas.models` | `loom.schemas.config.models` |
| `loom.schemas.prompt` | `loom.schemas.config.prompt` |
| `loom.schemas.tool` | `loom.schemas.config.tool` |
| `loom.schemas.hook` | `loom.schemas.config.hook` |
| `loom.schemas.retry` | `loom.schemas.config.retry` |
| `loom.schemas.sessions` | `loom.schemas.config.sessions` |
| `loom.schemas.conversations` | `loom.schemas.config.conversations` |
| `loom.schemas.evals` | `loom.schemas.config.evals` |
| `loom.schemas.loom` | `loom.schemas.config.loom` |
| `loom.schemas.agent_summary` | `loom.schemas.config.agent_summary` |

Integrators may use `from loom import AgentRequest, AgentResponse, LoomContext, LoomSession` or import the same symbols (plus other request/response helpers) from `loom.schemas` per `loom.schemas.__all__`.

## [0.2.0] - 2026-04-06

### Changed

- **Breaking:** Runtime configuration loaders moved from `loom.core.*_loader` to the `loom.core.loaders` subpackage. Module files no longer use the `_loader` suffix; evaluation experiment loading lives in `loom.core.loaders.evaluator` (replaces `eval_loader`). There are no compatibility shims — update imports if you referenced the old modules directly.

### Migration

| Before | After |
|--------|-------|
| `loom.core.agent_loader` | `loom.core.loaders.agent` |
| `loom.core.app_loader` | `loom.core.loaders.app` |
| `loom.core.conversation_loader` | `loom.core.loaders.conversation` |
| `loom.core.eval_loader` | `loom.core.loaders.evaluator` |
| `loom.core.hook_loader` | `loom.core.loaders.hook` |
| `loom.core.model_loader` | `loom.core.loaders.model` |
| `loom.core.output_loader` | `loom.core.loaders.output` |
| `loom.core.prompt_loader` | `loom.core.loaders.prompt` |
| `loom.core.retry_loader` | `loom.core.loaders.retry` |
| `loom.core.session_loader` | `loom.core.loaders.session` |
| `loom.core.tool_loader` | `loom.core.loaders.tool` |

Public names exported from `loom.core` (`get_agent_config`, `build_agent`, etc.) are unchanged.

## [0.1.0] - 2026-04-02

Initial public release (Alpha).

### Added

**CLI**
- `loom init` — scaffold workspace (`loom.toml`, `weave/` layout, app config skeleton)
- `loom agent new <name>` — interactive or flag-driven agent scaffolding
- `loom agent run <name>` — interactive REPL or one-shot (`-m`) agent execution
- `loom agent list / view / edit / copy / remove / validate / stats` — full agent lifecycle commands
- `loom evals new / run / compare / failures / regression` — evaluation pipeline commands
- `loom doctor` — environment and project health checks (Python, AWS/Bedrock, project files)
- `loom version` — version info for loom and key dependencies

**Core / Loaders**
- `build_agent()` orchestrator: composes all loaders into a `strands.Agent` per invocation
- `model_loader` — Bedrock (primary), OpenAI, Gemini (experimental) via `ModelConfig`
- `prompt_loader` — inline string, file, or directory (concatenated) prompt strategies
- `tool_loader` — dynamic import from agent-local or shared tools directories
- `hook_loader` — built-ins + qualified imports + `weave/hooks/<name>.py`
- `session_loader` — pluggable session managers (DynamoDB via Strands)
- `conversation_loader` — pluggable conversation managers with optional summarisation
- `output_loader` — Pydantic-schema structured output via `agent.py` or `output.py`
- `retry_loader` — configurable retry strategies
- `app_loader` — per-environment `app.<env>.yml` overlays; defaults merge into agent YAML

**Public API**
- `LoomAgent` — validate-at-construction, build-at-invocation agent wrapper (Lambda-compatible)
- `LoomAgent.invoke(AgentRequest) → AgentResponse` — typed request/response with token counts, latency, model metadata
- `LoomAgent.as_tool()` — expose agent as a Strands tool for multi-agent composition
- `LoomEvals` — programmatic evaluation runner

**Observability**
- Per-invocation metrics appended to `.loom/stats/{agent}.jsonl`
- `stats_service` aggregates and surfaces metrics via `loom agent stats`

**Built-in Hooks**
- `LoggingHook` — structured invocation logging
- `ToolTrackerHook` — records tool call names and results
- `RateLimitHook` — token-bucket rate limiting per agent

**Schemas**
- Pydantic models for all config types: `AgentConfig`, `AppConfig`, `ModelConfig`, `PromptConfig`, `SessionConfig`, `ConversationConfig`, `RetryConfig`, `HookConfig`, `OutputConfig`

**Testing**
- `loom.testing` helpers: `MockLoomAgent`, `_make_strands_result()` for unit tests without real LLM calls
- 440+ unit tests; coverage threshold enforced at 60 %

**CI/CD**
- GitHub Actions: lint (`ruff`), type-check (`mypy`), tests with coverage upload (Codecov)
- Release workflow: `uv build` + PyPI trusted publishing + GitHub Release on `v*` tags
- `pre-commit` hooks: ruff, mypy, conventional commits enforcement

[Unreleased]: https://github.com/jdbaigorria/loom-dev/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/jdbaigorria/loom-dev/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/jdbaigorria/loom-dev/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/your-org/loom/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/your-org/loom/releases/tag/v0.1.0
