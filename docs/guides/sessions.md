# Sessions

Sessions persist conversation history across invocations. Loom ships two backends: **file** (local disk) and **S3** (object storage), plus a **custom** passthrough for any other store. All are configured in `warp/config/app.yml`.

## Default: file session

```yaml title="warp/config/app.yml"
session:
  provider: file
  config:
    path: .loom/sessions
```

Session data is stored as files under `.loom/sessions/`. The directory is created automatically.

## S3 session

```yaml title="warp/config/app.yml"
session:
  provider: s3
  config:
    bucket: my-sessions-bucket
    prefix: loom/sessions/
```

Requires `boto3` (`pip install "loom-declarative[aws]"`) and appropriate IAM permissions.

## Custom session (DynamoDB, Redis, …)

Loom ships only `file` and `s3`. Any other backend plugs in by dotted `import_path` — Loom imports your `SessionManager` subclass and constructs it with the active `session_id` plus every key under `config` as a keyword argument. Loom validates nothing inside `config` and ships no adapter of its own (mirroring the model `custom` escape hatch).

```yaml title="warp/config/app.yml"
session:
  provider: custom
  import_path: my_pkg.sessions:DynamoSessionManager
  config:
    table_name: agent-sessions
    region_name: us-east-1
```

Your class must subclass the Strands `SessionManager` and accept `session_id` in its constructor:

```python
from strands.session import SessionManager

class DynamoSessionManager(SessionManager):
    def __init__(self, session_id: str, *, table_name: str, region_name: str):
        ...
```

## Disabling sessions

To run stateless (no persistence):

```yaml title="warp/config/app.yml"
session: null
```

## How sessions work

Each build is identified by `session_id` on the `LoomSession` passed to `build_agent`. Loom passes it to Strands' session manager, which loads prior conversation history at build time and persists each new turn after.

```python
from loom import build_agent, LoomSession

# Build with a session_id — history loaded automatically if it already exists
session = LoomSession(session_id="conv-abc", user_id="u-001")
agent = build_agent("my_agent", session)

result1 = agent("My order is #12345. What's the status?")

# A later request with the same session_id — rebuild, history is loaded again
agent2 = build_agent("my_agent", LoomSession(session_id="conv-abc", user_id="u-001"))
result2 = agent2("And what about the return policy?")
# The agent remembers the order number from the first turn (loaded from the session store)
```

For a *single* live process holding the conversation in memory across turns instead, skip session persistence and just reuse the same built `agent` — see [Conversation management](conversations.md).

## Session ID conventions

Use unique, stable identifiers for `session_id`:
- Per-conversation: a UUID generated when the conversation starts
- Per-user: `f"user-{user_id}"` for single-conversation-per-user flows
- Stateless: a fresh UUID each call (equivalent to `session: null` in app.yml)

```python
import uuid
session_id = str(uuid.uuid4())  # unique per conversation
```

## Conversation management

Sessions store raw message history. **Conversation management** controls how that history is sent to the model (truncation, summarization). See [Conversation management](conversations.md) for details.

`storage` in `app.yml` is a different knob. It is the shared backend (`local`, `s3`, or `memory`) for Strands subsystems that do not set a store of their own, including file memory. An explicit `session` block still owns conversation history.
