# Observability

Loom provides two levels of observability: built-in **invocation metrics** (always on) and optional **OpenTelemetry export** (for production tracing with any OTLP-compatible backend).

## Invocation metrics

Every `loom.dev.run_dev` call (which backs `loom agent run`/`dev` and the eval runner) appends a record to `.loom/stats/<agent_name>.jsonl`. No configuration needed. It's a dev-only convenience — in production your backend logs `response.usage` itself, since it drives the native Strands agent directly.

```bash
loom agent stats my_agent
```

```
agent: my_agent   runs: 47   avg_tokens: 832   avg_latency: 1240ms
  p50: 1100ms   p95: 2800ms   p99: 4200ms
  last run: 2026-06-10T09:15:22  tokens: 921  latency: 1380ms
```

### Metrics record schema

Each line in `.loom/stats/<name>.jsonl` contains:

| Field | Type | Description |
|---|---|---|
| `ts` | ISO 8601 | When the invocation completed |
| `session_id` | string | From the `LoomSession` |
| `user_id` | string | From the `LoomSession` |
| `system_prompt_tokens` | int | Estimated (chars/4) system-prompt size |
| `metrics` | object | Strands' own `agent.metrics.get_summary()` verbatim — token usage, duration, tool usage |

`loom agent stats` aggregates from `metrics` — no fields are re-derived at write time.

### Accessing metrics from Python

```python
from loom.dev import run_dev

run = run_dev("my_agent", "hello", session)
meta = run.response.metadata

print(meta.total_tokens)       # int
print(meta.response_time_ms)   # float
print(meta.model_id)           # str
print(meta.input_tokens)       # int
print(meta.output_tokens)      # int
print(meta.tool_calls)         # list[str]
print(meta.model_attempts)     # list[dict] — set when model uses fallback or a classifier
```

After a fallback, `model_id` is the candidate that answered, not the first name in the YAML. `model_attempts` lists each try as `{candidate, model_id, outcome}`. The same two fields are written into the stats record.

## Turn metrics

`meta.raw_metrics` is Strands' `get_summary()` verbatim, and it **accumulates** every turn the agent instance ran. `meta.turn` is the same data projected onto this turn only, as a frozen `TurnMetrics`:

```python
turn = run.response.metadata.turn

turn.duration_ms   # sum of the turn's cycles
turn.model_ms      # time inside model calls (stream_messages wall clock)
turn.tools_ms      # time inside tool calls
turn.other_ms      # max(0, duration - model - tools)
turn.usage         # tokens of this invocation: inputTokens, outputTokens, cacheRead…
turn.tool_errors   # {"search": 1}
for cycle in turn.cycles:
    cycle.model    # ModelCall(total_ms, latency_ms, first_token_ms) — provider timings when reported
    cycle.tools    # (ToolCall(tool_use_id, name, elapsed_ms, status), ...)
```

It never carries message text or tool arguments, so it is safe to log or return to a client.

Outside `run_dev` — a backend that drives the Strands agent itself — project the summary with `loom.turn_metrics`:

```python
from loom import turn_metrics, turn_metrics_of

turn = turn_metrics(result.metrics.get_summary())       # agent built for this turn

since = len(agent.event_loop_metrics.traces)             # agent reused across turns
agent("next question")
turn = turn_metrics_of(agent, since_trace=since)
```

How the numbers are read:

- Each `Cycle N` trace ends before the recursive call into the next cycle, so summing cycles does not count the next answer twice. The `Recursive call` trace is skipped.
- Parallel tools overlap, so `tools_ms` can exceed the wall clock; `other_ms` floors at 0.
- A cycle that never ended (the turn failed inside it) has `complete=False` and `total_ms` is the sum of its finished children. Its finished tools are still listed.
- A trace without the expected fields is skipped, never raised on.

## Metrics hook

The built-in `metrics` hook computes `TurnMetrics` at the end of every invocation and hands it to a sink — in any host, with or without a harness. Declare it once for every agent:

```yaml title="warp/config/app.yml"
defaults:
  hooks:
    - metrics                                   # sink: log
```

It runs on failed turns too (`outcome: error`, with the tools that ran), and on a reused agent it reports only the turn.

### Sinks

| `sink` | What it does |
|---|---|
| `log` (default) | One `INFO` line per turn on the `loom.metrics` logger, with `extra={"turn": ..., "context": ...}` for JSON formatters. Silent unless the host enables `loom.metrics` at `INFO`. |
| `emf` | CloudWatch Embedded Metric Format: JSON lines to stdout that CloudWatch Logs turns into metrics. No AWS SDK, no `PutMetricData`. |
| `module:function` | Your function, called as `function(metrics: TurnMetrics, context: TurnContext)`. Use it to publish with Powertools, OTel metrics or anything else. |

`TurnContext` carries `agent`, `session_id`, `user_id`, `outcome` (`ok` / `error`) and `stop_reason` — never message text or `invocation_state`.

```yaml
defaults:
  hooks:
    - metrics:
        sink: emf
        namespace: Acme/Agents
        service: acme                           # optional: adds a service dimension
        include: [invocation, breakdown, tools] # default: all three
        enabled: ${oc.env:LOOM_METRICS_ENABLED,true}
```

`namespace`, `service` and `include` only apply to `emf`. `enabled: false` registers no callbacks; it accepts the strings an `${oc.env:...}` interpolation yields.

### EMF metrics

| Group | Dimensions | Metric | Unit |
|---|---|---|---|
| `invocation` | `agent` (+`service`) | `Invocations` (1), `InvocationErrors` (0/1), `InvocationDuration` | Count, Count, Milliseconds |
| | | `InputTokens`, `OutputTokens`, `TotalTokens` — only on `ok` | Count |
| `breakdown` | `agent` (+`service`) | `ModelDuration`, `ToolsDuration`, `OtherDuration` | Milliseconds |
| | | `Cycles` | Count |
| `tools` | `agent`, `tool` (+`service`) | `ToolDuration`, `ToolInvocations` (1), `ToolErrors` (0/1) — one line per call | Milliseconds, Count, Count |

`session_id`, `user_id`, `outcome` and `stop_reason` travel on every line as properties, never as dimensions: each dimension combination is billed as a separate metric.

### With a harness that also counts turns

A harness that publishes its own per-turn metrics (Weave's `EmfTurnObserver`) already counts turns, errors — build failures included — and tokens. Keep this hook to what the harness cannot see from outside the agent:

```yaml
defaults:
  hooks:
    - metrics: { sink: emf, namespace: Acme/Agents, include: [breakdown, tools] }
```

Including `invocation` there would count tokens twice.

### Limits

- A build that fails never creates the agent, so the hook never runs. Count those in the host.
- An agent that declares its own `hooks` replaces `defaults.hooks` and loses `metrics` silently — repeat it in that agent.
- In a workflow the hook runs once per node, with `agent` set to the node.
- `kind: bidi` rejects the hook at build time: a full-duplex session has no invocation events.
- A turn cancelled by another hook (`BeforeInvocationEvent.cancel`) ends without a result and is reported as `error`.

## OpenTelemetry export

Enable the OTel exporter that Strands already emits traces for — agent invocations, model calls, tool executions — with a single `telemetry` block in `warp/config/app.yml`.

```yaml title="warp/config/app.yml"
telemetry:
  enabled: true
  exporter: otlp        # or: console
  metrics: false        # set true to export metrics as well
  service_name: my-agents-service
  trace_attributes: { app: billing, team: payments }
  baggage_attributes: { tenant: acme }
```

When you declare `trace_attributes` or `baggage_attributes`, Loom adds `session.id` and `user.id` from the `LoomSession`. A key you wrote yourself wins over those two. Omit both maps and Loom passes neither argument. `kind: bidi` rejects these attributes.

### OTLP endpoint

The endpoint, headers, and protocol come from the standard `OTEL_EXPORTER_OTLP_*` environment variables:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io
export OTEL_EXPORTER_OTLP_HEADERS="x-honeycomb-team=YOUR_API_KEY"
```

This makes Loom compatible with any OTLP collector without library-specific configuration.

### Console exporter (for local debugging)

```yaml
telemetry:
  enabled: true
  exporter: console
```

Prints spans to stdout — useful for local development without a collector.

### Supported backends

Any OTLP-compatible collector works:

| Backend | Notes |
|---|---|
| [Langfuse](https://langfuse.com) | LLM-native tracing + evals |
| [Jaeger](https://jaegertracing.io) | Open source distributed tracing |
| [Honeycomb](https://honeycomb.io) | Observability platform |
| [Grafana Tempo](https://grafana.com/oss/tempo/) | Via OTLP receiver |
| AWS X-Ray | Via OTLP → ADOT collector |
| Any OpenTelemetry Collector | Standard OTLP receiver |

### Feature detection

Telemetry setup is **feature-detected**: on a Strands build without OTel support, Loom logs a warning and continues. It never raises an error that breaks your app.

It is also **idempotent**: calling setup multiple times (e.g., in tests or when multiple agents are built in the same process) is safe.

## Log level

Control Loom's own log verbosity in `app.yml`:

```yaml
log_level: INFO    # DEBUG | INFO | WARNING | ERROR | CRITICAL
```

Set `DEBUG` during development to see tool calls, prompt construction, and model parameters in the logs.
