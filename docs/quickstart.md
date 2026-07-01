# Quickstart

Build your first agent in under 5 minutes.

## Prerequisites

Install Loom with the CLI extra, pinned to a [release tag](https://github.com/jdbaigorria/loom-dev/tags):

```bash
pip install "loom-declarative[all] @ git+https://github.com/jdbaigorria/loom-dev@vX.Y.Z"
```

## 1. Initialize a project

```bash
mkdir my-project && cd my-project
loom init
```

This creates:
```
my-project/
├── loom.toml           # workspace settings
└── warp/
    ├── config/
    │   └── app.yml     # app-level config (region, session, defaults)
    ├── hooks/
    └── workflows/
```

## 2. Create an agent

```bash
loom agent new assistant
```

This scaffolds:
```
warp/agents/assistant/
├── config/
│   ├── assistant.yml   # agent config (edit this)
│   └── prompt.md       # system prompt (edit this)
└── tools/              # add .py tool files here
```

## 3. Edit the system prompt

```bash
# Open in your editor:
loom agent edit assistant
# or just:
$EDITOR warp/agents/assistant/config/prompt.md
```

```markdown title="warp/agents/assistant/config/prompt.md"
You are a helpful assistant. Answer questions clearly and concisely.
When you don't know something, say so.
```

## 4. Configure the agent

The generated `assistant.yml` already has sensible defaults. For a first test it works as-is:

```yaml title="warp/agents/assistant/config/assistant.yml"
name: assistant
description: "Helpful assistant"
model: default        # Claude 3.5 Sonnet on Bedrock
retry: low
system_prompt: prompt.md
```

## 5. Run it

```bash
# One-shot message:
loom agent run assistant -m "What is the capital of France?"

# Interactive REPL:
loom agent run assistant
```

You should see:
```
> You: What is the capital of France?
> Assistant: Paris is the capital of France.
```

## 6. Validate the config

```bash
loom agent validate assistant
```

This checks: YAML schema, prompt file exists, tools resolve, output class loads. Fast, no model call.

## 7. Dev loop (hot reload)

```bash
loom agent dev assistant
```

Edit `prompt.md` or `assistant.yml` while the REPL is running — Loom detects changes and rebuilds the agent before the next message. No restart needed.

---

## What just happened?

`loom agent run` builds the agent from its YAML and runs one turn through Loom's dev-only executor. In your own code:

```python
from loom import LoomSession
from loom.dev import run_dev

session = LoomSession(session_id="session-1", user_id="user-1")
run = run_dev("assistant", "What is the capital of France?", session)
print(run.response.answer)
```

`run_dev` is dev-only (it backs the CLI and the eval runner). In production, your backend builds the agent once with `build_agent` and drives the **native Strands object** directly — no Loom wrapper in the call path:

```python
from loom import build_agent, LoomSession

session = LoomSession(session_id="session-1", user_id="user-1")
agent = build_agent("assistant", session)          # → strands.Agent

result = agent("What is the capital of France?")    # native Strands call
print(result.message["content"][0]["text"])
agent.cleanup()
```

Use `build_agent` directly when you need conversation continuity (call the same agent across turns), interrupts, or to embed Loom in your own application; use `run_dev` for local iteration and evals. See [Running an agent](guides/agents.md#running-an-agent-python) and the [Python API](reference/python-api.md) reference.

---

## Next: add a tool

Create a file in `warp/agents/assistant/tools/`:

```python title="warp/agents/assistant/tools/get_weather.py"
from strands import tool

@tool
def get_weather(city: str) -> str:
    """Return the current weather for a city."""
    # replace with a real API call
    return f"Sunny, 22°C in {city}"
```

Declare it in `assistant.yml`:

```yaml
tools:
  - get_weather
```

Run again — the agent now has access to the `get_weather` tool.

See [Tools](guides/tools.md) for shared tools, MCP servers, tool parameters, and `tool_executor`.
