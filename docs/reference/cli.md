# CLI reference

The `loom` CLI requires the `[cli]` extra (`pip install "loom-declarative[cli]"`).

## loom init

Create `loom.toml` and the workspace skeleton in the current directory.

```bash
loom init
loom init --interactive           # wizard-style prompts
loom init --region us-west-2      # set AWS region
loom init --force                 # overwrite existing files
```

Creates:
```
.
├── loom.toml
└── warp/
    ├── config/
    │   └── app.yml
    ├── hooks/
    └── workflows/
```

---

## loom agent

### new

```bash
loom agent new <name>
loom agent new <name> --interactive   # wizard with prompts for model, tools, etc.
```

Scaffolds `warp/agents/<name>/` with config and prompt files.

### list

```bash
loom agent list
```

Lists all agents in `warp/agents/`.

### view

```bash
loom agent view <name>
```

Shows the resolved (merged with app defaults) agent YAML.

### edit

```bash
loom agent edit <name>
```

Opens `<name>.yml` in `$EDITOR` or `vi`.

### run

```bash
loom agent run <name>
loom agent run <name> -m "single message"   # one-shot
loom agent run <name> --env staging          # with environment override
```

Interactive REPL or one-shot invocation. Handles human-in-the-loop interrupts automatically.

### dev

```bash
loom agent dev <name>
loom agent dev <name> --env staging
```

Hot-reload REPL — rebuilds the agent on each file change before the next message. See [Dev loop](../guides/dev-loop.md).

### validate

```bash
loom agent validate <name>
```

Validates YAML schema, prompt files, tools, output class, and hooks. No model call.

### stats

```bash
loom agent stats <name>
```

Shows aggregate metrics from `.loom/stats/<name>.jsonl` (run count, average tokens, average latency, p50/p95/p99).

### copy

```bash
loom agent copy <src> <dst>
```

Clones an agent directory and updates `name:` in the YAML.

### remove

```bash
loom agent remove <name>
loom agent remove <name> --force   # skip confirmation prompt
```

Deletes the agent directory.

---

## loom workflow

### list

```bash
loom workflow list
```

Lists all workflows in `warp/workflows/`.

### validate

```bash
loom workflow validate <name>
```

Validates YAML schema and checks all referenced agents exist.

### run

```bash
loom workflow run <name>
loom workflow run <name> -m "message"   # one-shot
loom workflow run <name> --env staging
```

---

## loom evals

Provided by the `loom-declarative-evals` package. Install it directly, or via the `[evals]` extra (an alias).

### new

```bash
loom evals new <agent>
```

Creates `warp/agents/<agent>/evals/evals.yml` from a template.

### run

```bash
loom evals run <agent>
loom evals run <agent> --failures    # show only failing cases after run
loom evals run <agent> --regression  # compare against previous run after this run
```

### compare

```bash
loom evals compare <agent>
```

Shows evaluation history from all JSONL result files.

### failures

```bash
loom evals failures <agent>
```

Shows failed cases from the most recent run.

### regression

```bash
loom evals regression <agent>
loom evals regression <agent> --threshold 0.05   # alert if score drops > 5%
```

Compares the last two runs and reports regressions.

---

## loom doctor

```bash
loom doctor           # full checks: Python, project files, AWS, Bedrock
loom doctor --no-aws  # skip AWS/Bedrock checks
```

Verifies:
- Python version ≥ 3.11
- `loom.toml` and workspace exist
- AWS credentials (with `[aws]` extra)
- Bedrock model access for the configured region (with `[aws]` extra)

---

## loom version

```bash
loom version
```

Shows versions of `loom`, Python, `strands-agents`, and other key dependencies.

---

## Environment variables

| Variable | Description |
|---|---|
| `LOOM_ENV` | Default environment profile (overridden by `--env`) |
| `AWS_DEFAULT_REGION` | AWS region (overridden by `loom.toml` and `app.yml`) |
| `AWS_ACCESS_KEY_ID` | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTel endpoint (used when telemetry is enabled) |
| `OTEL_EXPORTER_OTLP_HEADERS` | OTel headers |
| `EDITOR` / `VISUAL` | Editor for `loom agent edit` |
