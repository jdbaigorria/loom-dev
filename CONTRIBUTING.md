# Contributing to LOOM

Thank you for your interest in contributing. This guide covers everything you need to go from zero to a merged pull request.

## Prerequisites

- Python ≥ 3.11 (3.14 recommended for development — the CI matrix covers 3.11–3.14)
- [uv](https://docs.astral.sh/uv/) (package manager)
- AWS credentials with Bedrock access (only needed for manual end-to-end testing — unit tests are fully mocked)

## Setup

```bash
git clone https://github.com/jdbaigorria/loom-dev
cd loom-dev
uv sync --all-packages --group dev --all-extras
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

Verify everything works:

```bash
uv run poe check   # format + lint + type-check
uv run pytest tests
```

## Development workflow

| Task | Command |
|------|---------|
| Format + lint + type-check | `uv run poe check` |
| Tests only | `uv run poe test` |
| Single test file | `uv run pytest tests/unit/test_core.py` |
| Single test | `uv run pytest tests/unit/test_core.py::ClassName::method` |
| By name pattern | `uv run pytest -k "test_build_agent"` |
| With coverage | `uv run pytest --cov=loom --cov-report=term-missing` |

## Commit messages

This repo enforces [Conventional Commits](https://www.conventionalcommits.org/) via `pre-commit`.

```
<type>(<optional scope>): <short description>

feat(cli): add --json flag to agent stats
fix(loaders): handle missing spec.loader in dynamic import
docs: update installation instructions
chore: bump strands-agents to 1.27.0
```

Allowed types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`, `perf`, `build`.

## Submitting a pull request

1. Fork the repository and create a branch from `dev` (not `main`).
2. Make your changes. Add or update tests for any modified behaviour.
3. Run `uv run poe check && uv run pytest tests` — both must pass.
4. Open a PR against `dev`. The title must follow the Conventional Commits format (the CI `commit-msg` check runs on PR titles too via branch protection).
5. Fill in the PR template. Link the related issue if one exists.

## Project layout

```
src/loom/
├── __init__.py                 # Public API: build, build_agent, build_workflow, discover, LoomSession
├── _entry.py                   # Console-script entry (guards missing [cli] extra)
├── dev.py                      # run_dev — dev-only one-shot executor (backs CLI + evals)
├── errors.py                   # Public exception surface (re-exports core.exceptions)
├── testing.py                  # Test helpers (MockModel, mock_llm)
├── adapters/strands/          # Anti-corruption layer — only place Strands is imported
│   ├── _resolve.py            # Version-tolerant symbol resolution
│   └── capabilities.py        # Feature detection (MCP, tool_executor, Graph…)
├── cli/                       # Typer CLI; plugins mount via the loom.cli entry-point group
│   ├── commands/              # One module per command group
│   └── renders/               # Rich renderers for agent/evals/project output
├── config/                    # Project-level config loading
│   ├── defaults.py            # Scalar defaults (region, session path, …)
│   ├── loom_config.py         # loom.toml schema (workspace_name)
│   └── profiles.py            # Built-in profiles + user deep-merge
├── core/
│   ├── builder.py              # build / build_agent — orchestrates loaders → Strands Agent
│   ├── workflow_builder.py     # build_workflow — orchestrates node agents → Graph/Swarm
│   ├── exceptions.py           # Typed exception hierarchy
│   ├── reload.py               # Cache-clear helpers for hot-reload dev loop
│   ├── response.py             # AgentResponse builders (pure functions)
│   ├── telemetry.py            # OTel setup (idempotent, feature-detected)
│   ├── loaders/                # One module per concern: agent, app, model, prompt…
│   └── paths/                  # WorkspacePaths, asset paths, workflow paths
├── ports/
│   └── config_source.py        # ConfigSource protocol — where declarative config comes from
└── schemas/
    ├── config/                 # Pydantic models for YAML config (agent, app, workflow…)
    ├── response.py              # AgentResponse, AgentResponseMetadata, InterruptInfo (public)
    ├── target.py                 # TargetInfo, TargetKind — discovery (public)
    └── context.py                # LoomSession (public)
```

**Anti-corruption layer:** All `strands` / `strands_evals` imports must go through `loom.adapters.strands`. Enforced by ruff rule `TID251`. This makes upstream breaking changes a one-file fix.

**Core loaders:** One module per concern under `src/loom/core/loaders/` (`agent.py`, `app.py`, `model.py`, `prompt.py`, `tool.py`, `workflow.py`, …). The orchestrator is `loom.core.builder`; paths and exceptions live at the `loom.core` root.

**Schemas:** Declarative / YAML models live under `src/loom/schemas/config/`. The public `loom.schemas` package re-exports only `response` and `context`/`target` (build/discovery API). Prefer `from loom import LoomSession, TargetInfo` and `from loom.schemas.response import AgentResponse` for integrators; import config types from `loom.schemas.config.<module>`.

## Reporting bugs or requesting features

Use the [GitHub issue templates](https://github.com/jdbaigorria/loom-dev/issues/new/choose) — they guide you through the information needed to triage quickly.
