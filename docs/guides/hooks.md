# Hooks

Hooks are Python callables that run **before** and/or **after** each agent invocation. Use them for logging, auditing, injecting context, or modifying responses without touching agent logic.

## Declaring hooks

```yaml title="warp/agents/my_agent/config/my_agent.yml"
hooks:
  - log_invocation             # built-in hook
  - my_custom_hook             # warp/hooks/my_custom_hook.py
  - audit_logger: { dest: s3 } # hook with parameters
```

## Writing a hook

Place hook files under `warp/hooks/`. A hook is a Python module that exposes a callable with the Strands hook signature:

```python title="warp/hooks/my_custom_hook.py"
import logging

logger = logging.getLogger(__name__)

def before_agent(agent_name: str, request, **kwargs):
    """Called before each agent invocation."""
    logger.info("Invoking agent=%s query_len=%d", agent_name, len(request.query))


def after_agent(agent_name: str, request, response, **kwargs):
    """Called after each agent invocation."""
    logger.info(
        "agent=%s tokens=%d latency_ms=%d",
        agent_name,
        response.metadata.total_tokens,
        response.metadata.response_time_ms,
    )
```

## Hook with parameters

Access parameters declared in the YAML via `kwargs`:

```python title="warp/hooks/audit_logger.py"
import json
import boto3

def after_agent(agent_name, request, response, dest="local", **kwargs):
    record = {
        "agent": agent_name,
        "session": request.session_id,
        "tokens": response.metadata.total_tokens,
    }
    if dest == "s3":
        boto3.client("s3").put_object(
            Bucket="my-audit-bucket",
            Key=f"logs/{agent_name}/{request.session_id}.json",
            Body=json.dumps(record),
        )
    else:
        print(json.dumps(record))
```

```yaml
hooks:
  - audit_logger: { dest: s3 }
```

## Qualified import path

Reference hooks from any importable module:

```yaml
hooks:
  - my_pkg.observability.record_invocation
```

## App-level default hooks

Apply hooks to all agents via `warp/config/app.yml`:

```yaml title="warp/config/app.yml"
defaults:
  hooks:
    - log_invocation
```

Agent-level hooks are appended to (not replaced by) the defaults.

## Order of execution

Hooks are called in the order they are declared. For `before_agent` hooks: defaults first, then agent-specific. For `after_agent`: same order.

!!! note
    Hook files are loaded via `importlib` from the workspace. They run in the same process as Loom — they have full access to the Python environment but also inherit its security context. Do not load hook files from untrusted workspaces.
