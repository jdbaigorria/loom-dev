# Hooks

A hook is a Strands `HookProvider` **class**: it registers callbacks for agent lifecycle events (start and end of an invocation, model calls, tool calls). Use hooks for logging, auditing, metrics or blocking tool calls without touching agent logic.

Plugins are a separate list (`plugins` on the agent). A hook is a callback registration. A plugin is a Strands `Plugin` instance (`skills`, `context_offloader`, `goal`, or your own class). See [Memory, context, and control](memory-context-control.md).

## Declaring hooks

```yaml title="warp/agents/my_agent/config/my_agent.yml"
hooks:
  - logging                      # built-in
  - my_custom_hook               # warp/hooks/my_custom_hook.py
  - acme_app.hooks.Audit         # importable class (also acme_app.hooks:Audit)
  - audit_logger: { dest: s3 }   # with constructor params
```

An entry can be referenced three ways:

| Form | Resolves to |
|---|---|
| `logging` | A built-in (see below). |
| `pkg.module.Class` or `pkg.module:Class` | A class from installed or importable code. |
| `my_custom_hook` | `warp/hooks/my_custom_hook.py`. Loom instantiates the class named as the PascalCase of the file (`MyCustomHook`), or else the first class with `register_hooks`. |

The entry must resolve to a class. A function raises `HookLoadError` at load time.

## Writing a hook

```python title="warp/hooks/my_custom_hook.py"
import logging

from strands.hooks import AfterInvocationEvent, BeforeInvocationEvent, HookProvider

logger = logging.getLogger(__name__)


class MyCustomHook(HookProvider):
    def register_hooks(self, registry, **kwargs):
        registry.add_callback(BeforeInvocationEvent, self._before)
        registry.add_callback(AfterInvocationEvent, self._after)

    def _before(self, event: BeforeInvocationEvent) -> None:
        logger.info("Invocation started")

    def _after(self, event: AfterInvocationEvent) -> None:
        stop_reason = event.result.stop_reason if event.result else "error"
        logger.info("Invocation finished stop_reason=%s", stop_reason)
```

A tool-level hook works the same way:

```python
from strands.hooks import AfterToolCallEvent, HookProvider


class ToolAudit(HookProvider):
    def register_hooks(self, registry, **kwargs):
        registry.add_callback(AfterToolCallEvent, self._on_tool)

    def _on_tool(self, event: AfterToolCallEvent) -> None:
        print(event.tool_use["name"], event.exception)
```

## Hook with parameters

`params` from the YAML are passed **once, to the constructor**, when the agent is built. They are not passed on each call.

```python title="warp/hooks/audit_logger.py"
import json

from strands.hooks import AfterInvocationEvent, HookProvider


class AuditLogger(HookProvider):
    def __init__(self, dest: str = "local") -> None:
        self.dest = dest

    def register_hooks(self, registry, **kwargs):
        registry.add_callback(AfterInvocationEvent, self._after)

    def _after(self, event: AfterInvocationEvent) -> None:
        record = {"ok": event.result is not None}
        if self.dest == "s3":
            ...  # upload
        else:
            print(json.dumps(record))
```

```yaml
hooks:
  - audit_logger: { dest: s3 }
```

## Built-in hooks

| Name | Params | What it does |
|---|---|---|
| `logging` | none | Logs the start and end of each invocation, with the stop reason. |
| `tool_tracker` | none | Logs each tool call and whether it completed or failed. |
| `rate_limit` | `max_calls` (default `20`) | Cancels tool calls once the per-invocation limit is exceeded. |

## App-level default hooks

Apply hooks to all agents via `warp/config/app.yml`:

```yaml title="warp/config/app.yml"
defaults:
  hooks:
    - logging
```

!!! warning "Agent hooks replace the defaults"
    Lists are **replaced**, not appended, when `defaults` is merged with the agent YAML. If an agent declares `hooks`, the `defaults.hooks` do not apply to it. To keep them, repeat them in the agent.

## Order of execution

`Before*` events run hooks in declaration order. `After*` events (`AfterInvocationEvent`, `AfterToolCallEvent`, `AfterModelCallEvent`, …) run in **reverse** order, so hooks nest like context managers.

## End-of-turn hooks run on failure too

Strands fires `AfterInvocationEvent` from a `finally` block. If the turn raises (for example the model is unavailable), the event still fires, with `event.result` set to `None`. A metrics hook on `AfterInvocationEvent` therefore also covers failed turns. Check `event.result is None` before reading from it.

!!! note
    Hook files are loaded via `importlib` from the workspace. They run in the same process as Loom — they have full access to the Python environment but also inherit its security context. Do not load hook files from untrusted workspaces.
