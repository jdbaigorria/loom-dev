# Creating agents

An **agent** in Loom is a YAML file (plus optional Python files) that declares everything the agent needs: model, prompts, tools, hooks, retries, session, and output schema. Loom validates the config at load time — misconfigured agents fail fast at startup, not mid-invocation.

## Scaffold a new agent

```bash
loom agent new my_agent
# or with the interactive wizard:
loom agent new my_agent --interactive
```

Creates:
```
warp/agents/my_agent/
├── config/
│   ├── my_agent.yml   # agent definition — edit this
│   └── prompt.md      # default system prompt
└── tools/             # agent-specific tool files
```

## Agent YAML reference

```yaml title="warp/agents/my_agent/config/my_agent.yml"
name: my_agent
description: "What this agent does — surfaced in discovery and when the agent is used as a tool"

# Model: profile name or inline (see Models guide)
model: default        # or: economic | powerful | any profile in profiles.toml

# Retry: profile name or inline
retry: low            # or: medium | high | { max_attempts: 5, initial_delay: 2, max_delay: 120 }

# System prompt: file path, inline string, or directory
system_prompt: prompt.md

# Tools (optional)
tools:
  - search_orders            # agent-local: warp/agents/my_agent/tools/search_orders.py
  - shared.knowledge_base    # shared: warp/agents/tools/knowledge_base.py

# Hooks (optional)
hooks:
  - log_invocation           # built-in or warp/hooks/log_invocation.py

# Structured output (optional)
output: my_pkg.schemas.OrderResponse   # dotted import path to a Pydantic model

# MCP servers (optional)
mcp_servers:
  - name: filesystem
    transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]

# Tool execution strategy (optional)
tool_executor: concurrent    # or: sequential (default: Strands default = concurrent)
```

## Model

Specify a **profile name** (resolved from built-ins or `warp/config/profiles.toml`) or an **inline config**:

```yaml
model: economic          # built-in profile → Claude 3.5 Haiku / Bedrock

# Short provider alias (no full path needed):
model:
  provider: openai
  params:
    model_id: gpt-4o
    client_args: { api_key: ${oc.env:OPENAI_API_KEY} }

# Full dotted path (escape hatch for custom classes):
model:
  import_path: my.pkg.CustomModel
  params:
    model_id: my-model
```

See [Models & providers](models.md) for the full list of built-in aliases and how to add custom ones.

## System prompt

Three forms accepted:

```yaml
# File path (relative to the agent's config/ directory):
system_prompt: prompt.md

# Inline string:
system_prompt: "You are a helpful assistant. Answer clearly."

# Directory (files concatenated in alphabetical order):
system_prompt: prompts/
```

See [Prompts](prompts.md) for multi-file prompts, variables, and caching.

## Tools

```yaml
tools:
  - search_orders          # loads warp/agents/my_agent/tools/search_orders.py
  - shared.knowledge_base  # loads warp/agents/tools/knowledge_base.py

  # With parameters:
  - search_orders: { max_results: 10 }
  - shared.knowledge_base: { index: products }
```

Tool files must define functions decorated with `@tool` from Strands:

```python title="warp/agents/my_agent/tools/search_orders.py"
from strands import tool

@tool
def search_orders(order_id: str) -> dict:
    """Search for an order by ID."""
    return {"order_id": order_id, "status": "shipped"}
```

See [Tools](tools.md) for shared tools, MCP servers, and tool parameters.

## Hooks

Hooks run before and after each agent invocation. Declare them by name:

```yaml
hooks:
  - log_invocation      # built-in
  - my_custom_hook      # warp/hooks/my_custom_hook.py
  - audit_logger: { destination: s3 }  # with parameters
```

See [Hooks](hooks.md) for built-in hooks and writing your own.

## Structured output

When `output:` is set, the agent returns a Pydantic model instead of a plain string. Loom imports the class at load time:

```yaml
output: my_app.schemas.OrderSummary
```

```python title="my_app/schemas.py"
from pydantic import BaseModel

class OrderSummary(BaseModel):
    order_id: str
    status: str
    estimated_delivery: str | None = None
```

```python
response = agent.invoke(request)
summary = response.output   # OrderSummary instance
print(summary.order_id, summary.status)
```

## App-level defaults

Declare defaults in `warp/config/app.yml` to apply them to all agents. Agent YAML wins on conflict:

```yaml title="warp/config/app.yml"
defaults:
  model: economic
  retry: low
  hooks:
    - log_invocation
```

## Running an agent (Python)

There are two ways to run an agent from Python — pick by whether you need a long-lived handle.

**Build and drive natively** — `build_agent`. Resolves the YAML and returns a ready `strands.Agent`; you own it from there:

```python
from loom import build_agent, LoomSession

session = LoomSession(session_id="s-1", user_id="u-1")
agent = build_agent("my_agent", session)     # validates config at build time (fail fast)

result = agent("What is the order status?")  # native Strands call
print(result.message["content"][0]["text"])

agent.cleanup()                               # release MCP connections
```

This is the shape a production backend uses: build once, call across turns for conversation continuity (see `examples/02_conversation/`), compose into a Swarm/Graph by hand, or resolve human-in-the-loop interrupts natively:

```python
result = agent("delete the prod bucket")
while getattr(result, "interrupts", None):
    answers = [
        {"interruptResponse": {"interruptId": it["id"], "response": input(f"{it['name']}: ")}}
        for it in result.interrupts
    ]
    result = agent(answers)      # same live agent, resumes in place
print(result.message["content"][0]["text"])
```

**Dev-only one-shot** — `loom.dev.run_dev`. Builds the target, runs one turn, records `.loom/stats/<name>.jsonl`, and tears it down — the same path `loom agent run` and the eval runner use. Never ships to production:

```python
from loom import LoomSession
from loom.dev import run_dev

session = LoomSession(session_id="s-1", user_id="u-1")
run = run_dev("my_agent", "What is the order status?", session)
print(run.response.answer, run.response.metadata.total_tokens)
```

`run_dev` is **polymorphic**: if `my_agent` is actually a [workflow](workflows.md) (`warp/workflows/my_agent.yml`) it runs that instead — same call. Pass `kind="agent"` or `kind="workflow"` to disambiguate a name that exists as both.

!!! tip
    `run_dev` always tears the target down after one turn, so it cannot hold a paused interrupt open across calls (the response may still *report* pending interrupts in `.interrupts`). Reach for `build_agent` directly when you need to answer them across separate calls.

## Listing and managing agents

```bash
loom agent list                   # list all agents
loom agent view my_agent          # show the resolved (merged) YAML
loom agent validate my_agent      # validate without calling the model
loom agent stats my_agent         # show invocation metrics
loom agent copy my_agent clone    # clone an agent
loom agent remove my_agent        # delete an agent
```

## Python override

If a more advanced setup is needed, place an `agent.py` in the agent directory. It must expose an `agent` variable:

```python title="warp/agents/my_agent/agent.py"
from loom import build_agent, LoomSession

# build_agent reads the YAML and assembles the Strands agent normally,
# then you can augment it:
session = LoomSession(session_id="s-1", user_id="u-1")
agent = build_agent("my_agent", session)
agent.some_extra_setup()
```

When `agent.py` is present, Loom imports `agent` from it instead of building from YAML.
