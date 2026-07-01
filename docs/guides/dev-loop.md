# Dev loop

`loom agent dev` is an interactive REPL that **hot-reloads** the agent whenever you save changes to its config, prompts, or tools. Edit and iterate without restarting.

## Usage

```bash
loom agent dev my_agent
```

```
ℹ  Booting up agent my_agent (env: default)...
✔  Agent 'my_agent' ready (model: economic)

my_agent — type 'exit' to quit, edit files to reload

You: hello
Agent: Hello! How can I help you today?

You: [you edit prompt.md and save]
ℹ  Change detected — rebuilding agent my_agent...
✔  Agent 'my_agent' reloaded.

You: hello
Agent: [responds with the updated prompt]
```

## What triggers a reload

Loom fingerprints the following files by modification time (mtime):

- `warp/agents/<name>/config/<name>.yml` — the agent config
- `warp/agents/<name>/config/prompt.md` (and any file referenced by `system_prompt`)
- `warp/agents/<name>/tools/*.py` — all tool files
- `warp/agents/tools/*.py` — shared tool files used by this agent

Any save to these files triggers a rebuild before the next message.

## Safe reloads

If the rebuild fails validation (bad YAML, missing file, schema error), Loom **keeps the previous working agent** and prints the error. You can fix the issue and try again — the REPL stays alive.

```
ℹ  Change detected — rebuilding agent my_agent...
✗  Reload failed: ValidationError: field 'model' — 'typo_profile' is not a known profile.
ℹ  Continuing with previous agent config.
```

## Environment

Use `--env` to load environment-specific overrides:

```bash
loom agent dev my_agent --env staging
```

This loads `warp/config/app.staging.yml` on top of the base config. Useful for testing different model profiles or retry settings without editing files.

## One-shot with dev mode

You can combine `--env` with `-m` for a single hot-patched invocation — useful for scripting:

```bash
LOOM_ENV=staging loom agent run my_agent -m "test message"
```

## Keyboard shortcuts

| Key | Action |
|---|---|
| `Ctrl+C` | Exit REPL |
| `Ctrl+D` | Exit REPL |
| `exit` / `quit` / `q` | Exit REPL |

## Compared to loom agent run

| Feature | `loom agent run` | `loom agent dev` |
|---|---|---|
| Interactive REPL | ✅ | ✅ |
| One-shot with `-m` | ✅ | — |
| Hot-reload on file change | — | ✅ |
| Intended for | Usage / testing | Development |

## Clearing caches

Behind the scenes, `loom agent dev` calls `clear_config_caches()` on each reload. This clears the `lru_cache` on profile loading and related config — so new `profiles.toml` values take effect immediately without a process restart.
