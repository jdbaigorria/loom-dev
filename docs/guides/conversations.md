# Conversation management

As conversations grow, sending the full history to the model becomes expensive and eventually hits context limits. Loom supports three **conversation strategies** to control how history is managed.

## Strategies

### none (default)

Full history is sent each turn. Suitable for short conversations:

```yaml title="warp/config/app.yml"
conversation: none
```

### sliding (sliding window)

Keeps only the last N turns. Oldest messages are dropped as the window fills:

```yaml
conversation: sliding

# or inline:
conversation:
  strategy: sliding_window
  config:
    window_size: 20                  # number of messages to keep
    should_truncate_results: true    # also truncate tool results
```

### summarize (summarizing)

Periodically summarizes older context into a compact representation, preserving recent messages verbatim:

```yaml
conversation: summarize

# or inline with tuning:
conversation:
  strategy: summarizing
  config:
    summary_ratio: 0.3               # summarize when history exceeds 30% of context
    preserve_recent_messages: 10     # always keep the last 10 messages verbatim
    summarization_agent:             # model used for summarization (default: economic)
      model_id: null                 # null → uses the 'economic' profile
      temperature: 0.1
      max_tokens: 1024
```

### custom

Any other strategy plugs in by dotted `import_path` — Loom imports your `ConversationManager` subclass and constructs it with the `config` params as keyword arguments. Loom validates nothing inside `config` and ships no manager of its own (mirroring the model `custom` escape hatch).

```yaml
conversation:
  strategy: custom
  import_path: my_pkg.history:TokenBudgetManager
  config:
    max_tokens: 8000
```

## Built-in profiles

Like models and retry, conversation strategies have named profiles:

| Profile | Strategy | Notes |
|---|---|---|
| `none` | Null strategy | Full history, no management |
| `sliding` | Sliding window | 20 messages, truncate results |
| `summarize` | Summarizing | 30% ratio, keep last 10 messages |

Reference by name in agent YAML or app defaults:

```yaml
conversation: sliding
```

## Custom profiles

Add conversation profiles to `warp/config/profiles.toml`:

```toml title="warp/config/profiles.toml"
[conversation.large_context]
strategy = "sliding_window"
config = { window_size = 50, should_truncate_results = false }
```

## Per-agent vs. app-level

Set a default in `warp/config/app.yml` and override per-agent:

```yaml title="warp/config/app.yml"
conversation: sliding          # default for all agents

defaults:
  conversation: sliding
```

```yaml title="warp/agents/summarizer/config/summarizer.yml"
# this agent handles long conversations — override to summarize
conversation: summarize
```

## Notes

- Conversation management applies to the context sent to the **model**. Session storage (disk/S3) always stores the complete history.
- The summarizing strategy calls a second model invocation to produce the summary. The `economic` profile is used by default to keep costs low.
- `summarization_agent` and `summarization_system_prompt` are mutually exclusive — provide one or neither.
