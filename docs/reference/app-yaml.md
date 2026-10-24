# App YAML schema

Full reference for `warp/config/app.yml`.

## Complete example

```yaml title="warp/config/app.yml"
# AWS region for Bedrock calls
region: us-east-1

# Log level for Loom internals
log_level: INFO   # DEBUG | INFO | WARNING | ERROR | CRITICAL

# Session storage backend
session:
  provider: file
  config:
    path: .loom/sessions
# session:
#   provider: s3
#   config:
#     bucket: my-sessions-bucket
#     prefix: loom/sessions/
# session: null   # disable sessions (stateless)

# Conversation management
conversation: none   # or: sliding | summarize | inline config

# Default values applied to all agents (agent YAML wins on conflict)
defaults:
  model: economic
  retry: low
  hooks:
    - log_invocation

# OpenTelemetry (optional)
telemetry:
  enabled: false
  exporter: otlp    # or: console
  metrics: false
  service_name: my-agents
```

## Environment overrides

Create `app.<env>.yml` for environment-specific settings. Load with `--env` or `LOOM_ENV`:

```yaml title="warp/config/app.staging.yml"
region: us-west-2
log_level: DEBUG
defaults:
  model: economic   # cheaper model in staging
```

```bash
loom agent run my_agent --env staging
# or:
LOOM_ENV=staging loom agent run my_agent
```

## Fields

### region

**Default:** `us-east-1`

AWS region for Bedrock API calls. Also configurable in `loom.toml` (workspace-level default).

### log_level

**Default:** `INFO`

Loom's internal log verbosity. Set `DEBUG` during development to trace prompt construction, tool loading, and model parameters.

### session

**Default:** file session at `.loom/sessions`

Two backends:

**File:**
```yaml
session:
  provider: file
  config:
    path: .loom/sessions   # directory path — created automatically
```

**S3:**
```yaml
session:
  provider: s3
  config:
    bucket: my-bucket
    prefix: sessions/my-app/
```

**Disabled:**
```yaml
session: null
```

### storage

**Default:** omitted (each subsystem keeps its own default)

Shared backend for session and context pieces that do not set a store of their own. An explicit store on that subsystem still wins.

```yaml
storage:
  local: { base_dir: .loom/storage }   # default base_dir is .loom/storage
storage:
  s3: { bucket: my-bucket, prefix: loom/, region_name: us-east-1 }
storage: memory
```

`s3` receives the per-run `boto_session` from `model_params`. `local` receives the app sandbox when one is declared. This is the only new field a `kind: bidi` agent accepts.

### conversation

**Default:** `none`

Controls how conversation history is sent to the model. Three options:

| Value | Behavior |
|---|---|
| `none` | Full history sent each turn |
| `sliding` | Last N messages only |
| `summarize` | Older context summarized |

Inline config:
```yaml
conversation:
  strategy: sliding_window
  config:
    window_size: 20
    should_truncate_results: true
```

See [Conversation management](../guides/conversations.md).

### defaults

**Default:** `null`

YAML block merged into every agent's config. Agent values win on conflict.

```yaml
defaults:
  model: economic
  retry: low
  conversation: sliding
  hooks:
    - log_invocation
```

### telemetry

**Default:** `null` (disabled)

OTel export config:

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `false` | Enable OTel export |
| `exporter` | `otlp` \| `console` | `otlp` | Export backend |
| `metrics` | bool | `false` | Export metrics (not just traces) |
| `service_name` | str \| null | `null` | Service name in spans |

The OTLP endpoint and headers come from the standard env vars:
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `OTEL_EXPORTER_OTLP_HEADERS`
- `OTEL_EXPORTER_OTLP_PROTOCOL`

See [Observability](../guides/observability.md).
