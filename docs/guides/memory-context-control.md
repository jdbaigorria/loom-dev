# Memory, context, and control

These fields are off until the YAML declares them.

## Context

`context: auto`, `agentic`, or `off` replaces the conversation manager. Set `conversation: none` when you use it. A stateful model has the same requirement. See [agent YAML](../reference/agent-yaml.md).

## Memory

```yaml
memory:
  stores:
    - file: { name: notes, description: "Facts about {user_id}" }
```

`{user_id}` and `{session_id}` come from the Loom session.

`builtin.kb` asks the model to call a knowledge base. A `bedrock_kb` memory store injects results before each turn and can write memories when `writable` is true. The Bedrock store uses the `boto_session` passed in `model_params` for that run.

Without a sandbox, SDK tools that run commands execute on the host, with no isolation. Declare `sandbox` in `app.yml` (`docker` or `ssh`). An agent can override it. SSH host-key checks and the option allowlist stay at the SDK defaults.

## Control

`interventions` run before a tool call. Omit `ask` to pause with an interrupt: `loom agent run` prints the prompt and resumes with `interruptResponse`. `ask: stdio` blocks on stdin inside the turn. `cedar` policies need the `cedar` extra (`pip install 'loom-declarative[cedar]'`).
