# Memory, context, and control

These fields stay off until the YAML names them. The schemas are in [Agent YAML](../reference/agent-yaml.md) and [App YAML](../reference/app-yaml.md). `examples/09_sdk_features` builds an agent that sets them, with a fake model and no network.

`kind: bidi` rejects every field on this page except `storage`.

## Context

`context` replaces the conversation manager:

```yaml
conversation: none
context: auto    # auto | agentic | off
```

`off` passes `False`. A dict is forwarded as the SDK config. `import_path` builds a custom manager. Any other `conversation` value (`sliding`, `summarize`, a custom strategy) is an error. A stateful model has the same rule: `conversation` must be `none`, and Loom does not pass a conversation manager.

## Plugins

```yaml
plugins:
  - skills: { skills: ./skills }
  - context_offloader: { max_result_tokens: 2500 }
  - goal: { goal: "The answer includes the ticket number", max_attempts: 3 }
  - my_pkg.plugins.AuditPlugin
  - audit    # warp/plugins/audit.py, class Audit
```

`skills`, `context_offloader`, and `goal` are built in. `context_injector` and `steering` need callables, so they are not in the registry: use a dotted path. Hooks stay on `hooks`. A plugin is a Strands `Plugin`, constructed on every `build`.

## Memory

```yaml
memory:
  stores:
    - file: { name: notes, description: "Facts about {user_id}" }
    - bedrock_kb:
        name: policies
        config: { knowledge_base_id: ABC123XYZ }
        scope: "{user_id}"
  search_tool: true
  add_tool: false
  injection: true
```

`{user_id}` and `{session_id}` come from the `LoomSession` at build time. A `file` store writes under `.loom/memory` unless the store or `app.yml` `storage` already has a backend. A `bedrock_kb` store receives the per-run `boto_session` from `model_params` as its Bedrock clients. A dotted key imports a custom store.

`builtin.kb` is a tool the model calls when it decides to. A `bedrock_kb` memory store injects matches before the turn and can write when `writable` is true.

## Control

`interventions` run before a tool call. Order is the YAML order.

```yaml
interventions:
  - hitl:
      allowed_tools: [search]
  - cedar:
      policies: policies/billing.cedar
```

Omit `ask` and HITL pauses with an interrupt. `loom agent run` prints the prompt and resumes with `interruptResponse`. `ask: stdio` reads stdin during the turn. A dotted path is an inline callback. Names in `allowed_tools` must be tools on the agent (`*` and `!name` are allowed; the bare name still has to exist).

`cedar` needs `pip install "loom-declarative[cedar]"`. Policy paths are read relative to the agent config directory.

## Sandbox and storage

Without a sandbox, SDK tools that run commands execute on the host, with no isolation.

```yaml title="warp/config/app.yml"
sandbox:
  docker: { container: loom-runner, working_dir: /work }
# or
sandbox:
  ssh: { host: runner.internal, working_dir: /srv/agent }
storage:
  local: { base_dir: .loom/storage }
```

An agent YAML `sandbox` overrides the app one. SSH host-key checks and the option allowlist stay at the SDK defaults unless you set `allow_unknown_hosts` or `allow_unsafe_ssh_options`. `DockerSandbox` only stores these values at build time; it does not start a container. `local` storage receives that sandbox when one exists. `s3` storage receives the per-run `boto_session`.

## Background tools

```yaml
background_tasks: true
# or
background_tasks:
  always: [report]
  never: [search]
  max_concurrency: 4
```

`always`, `never`, and `agentic` name tools declared on the agent.

## Checkpointing (experimental)

`checkpointing: true` pauses between model and tool cycles (`stop_reason: checkpoint`). `loom agent run` resumes with `checkpointResume`. The marker does not include the conversation, so a restart still needs `session` in `app.yml`.

## Telemetry attributes

```yaml
telemetry:
  enabled: true
  trace_attributes: { app: billing }
  baggage_attributes: { tenant: acme }
```

Loom adds `session.id` and `user.id` to each map you declared. Your keys win. See [Observability](observability.md).
