# Contributing

Thank you for your interest in contributing to Loom. This guide covers setup, workflow, and conventions.

## Prerequisites

- Python ≥ 3.11 (3.14 recommended — the CI matrix covers 3.11–3.14)
- [uv](https://docs.astral.sh/uv/) package manager
- AWS credentials with Bedrock access (only for manual end-to-end tests — unit tests are fully mocked)

## Setup

```bash
git clone https://github.com/jdbaigorria/loom-dev
cd loom-dev
uv sync --all-packages --all-extras --group dev
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

Verify:

```bash
uv run poe check    # format + lint + type-check
uv run poe test     # run the test suite
```

## Development workflow

| Task | Command |
|---|---|
| Format + lint + type-check | `uv run poe check` |
| Tests only | `uv run poe test` |
| Single test file | `uv run pytest tests/unit/test_core.py` |
| Single test | `uv run pytest tests/unit/test_core.py::ClassName::method` |
| By name pattern | `uv run pytest -k "test_build_agent"` |
| With coverage | `uv run pytest --cov=loom --cov-report=term-missing` |
| Docs preview | `uv run mkdocs serve` |

## Codebase layers

```
src/loom/
├── __init__.py                 # Public API: build, build_agent, build_workflow, discover, LoomSession
├── _entry.py                   # Console-script entry (guards missing [cli] extra)
├── dev.py                      # run_dev — dev-only one-shot executor (backs CLI + evals)
├── errors.py                   # Public exception surface (re-exports core.exceptions)
├── testing.py                  # Test helpers (MockModel, mock_llm)
├── adapters/strands/           # Anti-corruption layer — only place Strands is imported
│   ├── _resolve.py             # Version-tolerant symbol resolution
│   └── capabilities.py         # Feature detection (MCP, tool_executor, Graph…)
├── cli/                        # Typer CLI; plugins mount via the loom.cli entry-point group
├── config/                     # Project-level config loading
│   ├── defaults.py             # Scalar defaults (region, session path)
│   ├── profiles.py             # Built-in profiles + user deep-merge
│   └── loom_config.py          # loom.toml schema
├── core/
│   ├── builder.py              # build / build_agent — orchestrates loaders → Strands Agent
│   ├── workflow_builder.py     # build_workflow — orchestrates node agents → Graph/Swarm
│   ├── exceptions.py           # Typed exception hierarchy
│   ├── loaders/                # One loader per concern: agent, app, model, prompt…
│   └── paths/                  # WorkspacePaths, asset paths
├── ports/
│   └── config_source.py        # ConfigSource protocol — where declarative config comes from
└── schemas/
    ├── config/                 # Pydantic models for YAML config
    ├── response.py              # AgentResponse, AgentResponseMetadata, InterruptInfo
    ├── target.py                 # TargetInfo, TargetKind (discovery)
    └── context.py                # LoomSession
```

**Anti-corruption layer:** All `strands` / `strands_evals` imports must go through `loom.adapters.strands`. Enforced by ruff rule `TID251`. Violating it fails `loom check`.

## Commit messages

This repo enforces [Conventional Commits](https://www.conventionalcommits.org/) via `pre-commit`:

```
<type>(<optional scope>): <short description>

feat(builtins): add domain-shaped apicall tool
fix(loaders): handle missing spec.loader in dynamic import
docs: update models guide with provider aliases
chore: bump strands-agents to 1.35.0
```

Allowed types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`, `perf`, `build`, `style`.

## Submitting a pull request

1. Fork and create a branch from `dev` (not `main`).
2. Make your changes. Add or update tests for any modified behavior.
3. Run `uv run poe check && uv run poe test` — both must pass.
4. Open a PR against `dev`. Title must follow Conventional Commits format.
5. Fill in the PR template. Link the related issue if one exists.

## Reporting bugs

Use the [GitHub issue tracker](https://github.com/jdbaigorria/loom-dev/issues). Include:
- Loom version (`loom version`)
- Python version
- Minimal reproducible example
- Full error traceback
