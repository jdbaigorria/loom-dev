# Tools

Tools extend what an agent can do — database queries, API calls, file operations, calculations. Loom loads tools automatically from Python files; you declare which ones an agent uses in its YAML.

## Writing a tool

Tools are regular Python functions decorated with `@tool` from Strands:

```python title="warp/agents/my_agent/tools/search_orders.py"
from strands import tool

@tool
def search_orders(order_id: str, include_history: bool = False) -> dict:
    """Search for an order by ID.

    Args:
        order_id: The order identifier.
        include_history: Whether to include status history.
    """
    # your implementation here
    return {
        "order_id": order_id,
        "status": "shipped",
        "tracking": "1Z999AA10123456784",
    }
```

!!! important
    The docstring is the tool's description sent to the model. Write it clearly — the model reads it to decide when and how to call the tool.

## Agent-local tools

Placed under `warp/agents/<name>/tools/`. Declared by filename stem:

```yaml
tools:
  - search_orders       # → warp/agents/my_agent/tools/search_orders.py
  - update_ticket       # → warp/agents/my_agent/tools/update_ticket.py
```

## Shared tools

Placed under `warp/agents/tools/`. Declared with the `shared.` prefix:

```yaml
tools:
  - shared.knowledge_base    # → warp/agents/tools/knowledge_base.py
  - shared.send_email        # → warp/agents/tools/send_email.py
```

Shared tools are available to all agents in the workspace, avoiding duplication.

## Declarative tool files (YAML)

A tool that specialises a builtin (see below) can live as a `{name}.yaml` file in the same `tools/` folders as Python tools — agent-local or shared — instead of being written inline in the agent YAML. The **file name is the tool name** (symmetric with `.py`, where the function name is the tool name), so the file must not set `name`.

```yaml
# warp/agents/my_agent/tools/get_pokemon.yaml
builtin: apicall                       # which builtin this file specialises
description: Fetch a Pokémon's data from PokéAPI by name or id.
bind:
  base_url: https://pokeapi.co/api/v2
  path: /pokemon/{name_or_id}
  method: GET
  select: [id, name, types, height, weight, stats, abilities]
expose:
  name_or_id:
    type: string
    required: true
    description: "Pokémon name (e.g. 'ivysaur') or id (e.g. '2')."
```

Reference it from the agent exactly like a Python tool — by stem, or with `shared.` if it lives in `warp/agents/tools/`:

```yaml
tools:
  - get_pokemon          # → tools/get_pokemon.yaml (or .py)
  - shared.lookup_user   # → warp/agents/tools/lookup_user.yaml
```

This makes a declarative tool a **reusable artifact**: define it once, reference it from many agents, keep the agent YAML to wiring. `${oc.env:...}` references inside the file are resolved at load, just like in the agent YAML.

A name must resolve to exactly one definition — having both `{name}.py` and `{name}.yaml` is a build error, and a YAML tool is referenced without inline params (its config lives in the file).

Use the inline `builtin.` form (below) for a quick, agent-specific one-off; use a tool file when the definition is reusable or you want to keep the agent YAML lean.

## Built-in tools

Loom ships ready-made tools you attach straight from YAML with the `builtin.` prefix — no Python file to write. Each builtin is a *factory* configured through params.

```yaml
tools:
  - builtin.kb:
      kb_ids: [docs, tickets]
  - builtin.apicall:
      name: weather_api
      base_url: https://api.weather.example.com
      allowed_paths: ["/v1/*"]
```

!!! note "Extras"
    `builtin.kb` needs `boto3` (the `aws` extra); `builtin.apicall` needs `requests` (the `tools` extra). Install both with `pip install loom-declarative[aws,tools]` (or `[all]`). They are imported lazily, so the rest of Loom works without them.

### `builtin.kb` — Knowledge-base search

Searches one or more Amazon Bedrock Knowledge Bases and returns merged, score-ranked passages. **One** tool fans out across every `kb_id` — the multi-KB behaviour lives inside the tool, so there is no name collision.

```yaml
tools:
  - builtin.kb:
      kb_ids: [docs, tickets]   # required: one or more KB ids (fan-out + merge)
      region: us-east-1         # default: us-west-2
      max_results: 10           # results requested per KB before merging
      score_threshold: 0.7      # drop passages below this relevance score
      search_type: HYBRID       # HYBRID or SEMANTIC
      top_k: 5                  # passages kept after the cross-KB merge
      name: kb_search           # Strands tool name (default: kb_search)
```

The model calls it with a `query` and may optionally pass `kb_id` to target a single knowledge base; omitting it searches all of them.

### `builtin.apicall` — HTTP tool

Calls a pre-configured HTTP API. It has two modes, chosen by whether you declare `expose`:

| Mode | You declare | The model sees | Use it for |
|------|-------------|----------------|------------|
| **Domain** (recommended) | `bind` + `expose` | A named, typed tool (`get_pokemon(name_or_id)`) | Any operation you can name |
| **Generic** | `base_url` + `allowed_paths` | A generic HTTP proxy (`path`, `method`, `body`) | Exploring an API; can't enumerate endpoints |

#### Domain mode (recommended)

The model fills the semantic params in `expose`; the framework assembles the request from the `bind` template. The model **never builds a path**, so it cannot mis-format one — the whole class of path-formatting hallucinations is structurally impossible.

```yaml
tools:
  - builtin.apicall:
      name: get_pokemon
      description: Fetch a Pokémon's data from PokéAPI by name or id.   # REQUIRED in domain mode
      bind:                                  # fixed template — the model never sees it
        base_url: https://pokeapi.co/api/v2
        path: /pokemon/{name_or_id}          # {param} placeholders, filled at call time
        method: GET
      expose:                                # this becomes the model-facing inputSchema
        name_or_id:
          type: string
          required: true
          description: "Pokémon name (e.g. 'ivysaur') or numeric id (e.g. '2')."
```

Placeholders can appear in `path`, `query`, `body` and `headers`. A whole-string placeholder (`"{n}"`) preserves the param's native type (int, bool, …); path segments are URL-encoded and `..` is rejected (no path traversal). Optional params use their `default` when the model omits them.

!!! tip "Trim the response with `select`"
    Many APIs return large payloads (PokéAPI's pokemon object is ~200 KB). The whole tool result is injected into the conversation, so one chatty endpoint can overflow the context window. Add `select` to `bind` to keep only the fields you need:

    ```yaml
    bind:
      base_url: https://pokeapi.co/api/v2
      path: /pokemon/{name_or_id}
      method: GET
      select: [id, name, types, height, weight, stats, abilities]  # the rest is dropped
    ```

    Entries are dotted paths into nested dicts (`sprites.front_default`); missing paths are skipped and non-dict (array) responses pass through unchanged.

```yaml
  - builtin.apicall:
      name: create_ticket
      description: Open a support ticket for a citizen.
      bind:
        base_url: https://api.example-gov.example
        path: /tickets
        method: POST
        static_headers:                      # sent verbatim (not templated)
          Authorization: "Bearer ${oc.env:TICKETS_API_TOKEN}"
        body:
          dni: "{dni}"
          subject: "{subject}"
          priority: "{priority}"
      expose:
        dni:      { type: string, required: true,  description: "Citizen document number." }
        subject:  { type: string, required: true,  description: "Short ticket title." }
        priority: { type: string, default: "normal", enum: ["low", "normal", "high"],
                    description: "Ticket priority." }
```

Two interpolation syntaxes, resolved at different times: `${...}` (env/secrets) is resolved **at load**, before the tool exists; `{param}` is resolved **at runtime** from the model's arguments. Keep them separate.

#### Generic mode

Base URL, headers and the path allow-list are fixed in YAML; the model chooses the path, method and body at call time. A fragile escape hatch — prefer domain mode whenever you can name the operation.

```yaml
tools:
  - builtin.apicall:
      name: weather_api                 # REQUIRED — the Strands tool name
      base_url: https://api.weather.example.com
      allowed_paths: ["/v1/*"]          # REQUIRED — glob allow-list (SSRF guard)
      headers:
        Authorization: "Bearer ${oc.env:WEATHER_TOKEN}"
      timeout: 8.0
      clean_response: true              # strip empty values from the JSON response
```

In either mode, `name` is **required** so you can mount several endpoints on one agent without a collision — each instance becomes a distinctly-named Strands tool.

!!! warning "Allow-list is mandatory (generic mode)"
    `allowed_paths` cannot be empty — an unrestricted HTTP tool is an SSRF risk. Requests to a path outside the list are refused before any network call is made. Domain mode needs no allow-list: the path is a fixed template, not model-chosen.

### Using them

Once declared, builtins are just tools — the agent decides when to call them. You build and call the agent normally:

```python
from loom import build_agent, LoomSession

# The agent above (kb_search + weather_api + billing_api) used like any other:
session = LoomSession(session_id="s-1", user_id="u-1")
agent = build_agent("support", session)
result = agent("What's our refund policy?")
print(result.message["content"][0]["text"])   # the model called kb_search under the hood
```

See the runnable [`examples/08_builtins`](https://github.com/jdbaigorria/loom-dev/tree/dev/examples/08_builtins) for a full agent wired with both builtins (it resolves the tools offline, no AWS/HTTP needed).

## Tool parameters

Pass configuration to a tool at declaration time using the single-key dict syntax:

```yaml
tools:
  - search_orders: { max_results: 20, region: "us-east" }
  - shared.knowledge_base: { index: products, top_k: 5 }
```

The params are available to the tool via `ToolContext`:

```python
from strands import tool
from strands.types.tools import ToolUse

@tool
def search_orders(order_id: str, **kwargs) -> dict:
    max_results = kwargs.get("max_results", 10)
    ...
```

## Tool execution strategy

Control how multiple tool calls in a single turn are executed:

```yaml
tool_executor: concurrent    # run tool calls in parallel (default Strands behavior)
tool_executor: sequential    # run tool calls one by one
```

Omit `tool_executor` to use the Strands default (concurrent). This is feature-detected — on a Strands build without pluggable executors, loading fails with a clear upgrade hint.

## MCP servers

Connect [Model Context Protocol](https://modelcontextprotocol.io) servers to expose external tools to the agent. Tools from each server are namespaced by the server's `name`:

```yaml
mcp_servers:
  - name: filesystem
    transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]

  - name: github
    transport: http
    url: https://mcp.example.com/github
    headers:
      Authorization: "Bearer ${oc.env:GITHUB_TOKEN}"
```

A tool from the `filesystem` server named `read_file` becomes `filesystem_read_file` in the agent's tool list.

### stdio transport

Launches a local process:

```yaml
mcp_servers:
  - name: my_server
    transport: stdio
    command: python
    args: ["-m", "my_mcp_server"]
    env:
      MY_CONFIG: "/path/to/config"
```

### http / sse transport

Connects to a remote server:

```yaml
mcp_servers:
  - name: remote_tools
    transport: http      # or: sse
    url: https://tools.example.com/mcp
    headers:
      Authorization: "Bearer ${oc.env:TOOLS_API_KEY}"
```

MCP connections open at build time and stay open across turns — call `agent.cleanup()` when you're done with the agent to close them. `loom.dev.run_dev` (dev-only) does this for you after each one-shot call.

## Tool directory (all tools in folder)

If you declare a directory instead of a specific file, Loom loads all `*.py` files in it:

```yaml
tools:
  - tools/             # loads all .py files in warp/agents/my_agent/tools/
```

## Python API

Tools are also accessible programmatically when building agents directly:

```python
from loom.core.builder import build_agent

agent = build_agent("my_agent")
# agent.tools contains the loaded Strands tool list
```
