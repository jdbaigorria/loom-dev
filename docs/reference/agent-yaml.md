# Agent YAML schema

Full reference for `warp/agents/<name>/config/<name>.yml`.

## Complete example

```yaml
name: my_agent
description: "Customer support agent for Acme Corp"

# Model
model: economic
# model:
#   provider: openai
#   params:
#     model_id: gpt-4o
#     client_args: { api_key: ${oc.env:OPENAI_API_KEY} }

# Retry
retry: low
# retry:
#   max_attempts: 5
#   initial_delay: 2.0
#   max_delay: 120.0

# System prompt
system_prompt: prompt.md
# system_prompt: "Inline prompt string"
# system_prompt: prompts/   # directory — files concatenated in alphabetical order
# system_prompt:
#   prompt: prompt.md
#   cache: true
#   context: "Extra context appended after the prompt"

# Tools (optional)
tools:
  - search_orders                       # agent-local tool
  - shared.knowledge_base               # shared tool
  - search_orders: { max_results: 20 }  # tool with params
  - builtin.kb: { kb_ids: [docs] }      # built-in tool (shipped with Loom)

# Hooks (optional)
hooks:
  - log_invocation
  - my_pkg.hooks.audit_logger
  - my_hook: { param: value }

# Structured output (optional)
output: my_pkg.schemas.OrderSummary   # dotted import path to a Pydantic model

# MCP servers (optional)
mcp_servers:
  - name: filesystem
    transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
  - name: remote_api
    transport: http
    url: https://api.example.com/mcp
    headers:
      Authorization: "Bearer ${oc.env:API_KEY}"

# Tool execution (optional)
tool_executor: concurrent   # or: sequential
```

## Fields

### name

**Required.** Internal name used to locate the agent's directory and YAML.

### description

**Default:** `"Agent created by Loom"`

Human-readable description. Surfaced in catalog/discovery listings and used as the routing signal when the agent is wrapped as a tool (`Agent.as_tool`) — keep it accurate and specific.

### model

**Default:** `"default"` (Claude 3.5 Sonnet on Bedrock)

Profile name (string) or inline config:

| Form | Example |
|---|---|
| Profile name | `model: economic` |
| Provider alias | `model: { provider: openai, params: { model_id: gpt-4o } }` |
| Full import path | `model: { import_path: strands.models.openai.OpenAIModel, params: {} }` |

See [Models & providers](../guides/models.md).

### retry

**Default:** `"low"` (3 attempts, 1s initial delay, 60s max)

Profile name or inline:

| Form | Example |
|---|---|
| Profile name | `retry: medium` |
| Inline | `retry: { max_attempts: 5, initial_delay: 2, max_delay: 120 }` |

### system_prompt

**Default:** `"prompt.md"`

String (file path or inline text), or object with extended options:

```yaml
system_prompt:
  prompt: prompt.md      # required — path or inline string
  context: "..."         # optional — appended after prompt
  cache: false           # optional — enable prompt caching
  variables: {}          # optional — template variables
```

### tools

**Default:** `null` (no tools)

List of tool names. Each entry can be:
- A string: `search_orders` (agent-local) or `shared.tool_name` (shared)
- A single-key dict with params: `{ search_orders: { max_results: 10 } }`
- A `builtin.<name>` entry for a tool shipped with Loom (`builtin.kb`, `builtin.apicall`) — see [Built-in tools](../guides/tools.md#built-in-tools).

### hooks

**Default:** `null`

List of hook names. Each entry can be:
- A string: built-in name or `my_pkg.module.hook_func`
- A single-key dict with params: `{ my_hook: { key: value } }`

### output

**Default:** `null`

Dotted import path to a Pydantic `BaseModel` subclass. When set, the agent returns a validated model in `AgentResponse.output`.

### mcp_servers

**Default:** `null`

List of MCP server configs. Two transports:

**stdio** (local process):

| Field | Type | Description |
|---|---|---|
| `name` | str | Server identifier (prefixes tool names) |
| `transport` | `"stdio"` | |
| `command` | str | Executable to launch |
| `args` | list[str] | Arguments |
| `env` | dict | Extra environment variables |

**http / sse** (remote):

| Field | Type | Description |
|---|---|---|
| `name` | str | Server identifier |
| `transport` | `"http"` or `"sse"` | |
| `url` | str | Server URL |
| `headers` | dict | Request headers |

### tool_executor

**Default:** `null` (Strands default, currently concurrent)

| Value | Behavior |
|---|---|
| `concurrent` | Tool calls in a single turn run in parallel |
| `sequential` | Tool calls run one by one |
| *(omitted)* | Strands default |

`kind: bidi` does not accept `tool_executor`. Strands 1.57.2 removed that argument from `BidiAgent`, and Loom raises `AgentConfigError` instead of forwarding it.

### plugins

```yaml
plugins:
  - skills: { skills: ./skills }
  - context_offloader: { max_result_tokens: 2500 }
  - goal: { goal: "The answer includes the ticket number", max_attempts: 3 }
  - my_pkg.plugins.AuditPlugin
  - audit
```

`skills`, `context_offloader`, and `goal` are built in. A dotted path imports a class. A bare name loads `warp/plugins/<name>.py` and instantiates the PascalCase class. `kind: bidi` rejects `plugins`. Nothing is loaded when the field is omitted.

Feature-detected: on a Strands build without pluggable executors, setting this field raises a `LoomStrandsCompatError` at load time.
