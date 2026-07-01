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
```

## OpenTelemetry export

Enable the OTel exporter that Strands already emits traces for — agent invocations, model calls, tool executions — with a single `telemetry` block in `warp/config/app.yml`.

```yaml title="warp/config/app.yml"
telemetry:
  enabled: true
  exporter: otlp        # or: console
  metrics: false        # set true to export metrics as well
  service_name: my-agents-service
```

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
