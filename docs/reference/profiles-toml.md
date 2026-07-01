# profiles.toml

`warp/config/profiles.toml` extends or overrides Loom's built-in profiles for models, retry, and conversation. Your values are **deep-merged over the built-ins** — existing built-in profiles are preserved unless you explicitly override them.

## Location

```
warp/config/profiles.toml
```

Created (with commented examples) by `loom init`.

## Structure

```toml
# Model profiles
[model.<profile_name>]
provider    = "openai"                          # short alias
# import_path = "strands.models.openai.OpenAIModel"  # or full dotted path
params      = { model_id = "gpt-4o" }

# Retry profiles
[retry.<profile_name>]
max_attempts  = 6
initial_delay = 2
max_delay     = 120

# Conversation profiles
[conversation.<profile_name>]
strategy = "sliding_window"
config   = { window_size = 30 }

# Provider aliases
[providers]
my_provider = "my.pkg.CustomModel"
```

## Built-in model profiles

| Name | Provider | Model ID |
|---|---|---|
| `default` | Bedrock | `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| `economic` | Bedrock | `anthropic.claude-3-5-haiku-20241022-v1:0` |
| `powerful` | Bedrock | `anthropic.claude-3-5-sonnet-20241022-v2:0` |

## Built-in retry profiles

| Name | max_attempts | initial_delay | max_delay |
|---|---|---|---|
| `low` | 3 | 1s | 60s |
| `medium` | 4 | 2s | 90s |
| `high` | 5 | 3s | 120s |

## Built-in conversation profiles

| Name | Strategy | Notes |
|---|---|---|
| `none` | null | Full history, no management |
| `sliding` | sliding_window | window=20, truncate results |
| `summarize` | summarizing | ratio=0.3, preserve last 10 |

## Examples

### Add a GPT-4o profile

```toml
[model.gpt4]
provider = "openai"
params   = { model_id = "gpt-4o" }
```

Now any agent can use `model: gpt4`.

### Add a fast Bedrock profile

```toml
[model.fast]
import_path = "strands.models.bedrock.BedrockModel"
params      = { model_id = "anthropic.claude-3-5-haiku-20241022-v1:0" }
```

### Override the default model

```toml
[model.default]
import_path = "strands.models.openai.OpenAIModel"
params      = { model_id = "gpt-4o" }
```

Now `model: default` everywhere uses GPT-4o instead of Bedrock.

### Aggressive retry profile

```toml
[retry.aggressive]
max_attempts  = 8
initial_delay = 1
max_delay     = 180
```

### Custom conversation profile

```toml
[conversation.long_context]
strategy = "sliding_window"
config   = { window_size = 50, should_truncate_results = false }
```

### Custom provider alias

```toml
[providers]
internal_llm = "company.llm.InternalModel"
my_finetune  = "my.pkg.FinetunedBedrock"
```

Now any inline model config can use `provider: internal_llm`.

## Deep merge semantics

User values in `profiles.toml` are merged over built-ins at the profile level. Specifically:

- A `[model.fast]` block adds a new profile — built-ins (`default`, `economic`, `powerful`) are untouched.
- A `[model.default]` block overrides only the default profile — `economic` and `powerful` are untouched.
- `[providers]` is merged key by key — built-in aliases not listed in your file are preserved.
- Within a profile, only the fields you specify are overridden — unspecified fields keep built-in values.

## Using profiles

Reference a profile name anywhere `model:`, `retry:`, or `conversation:` is accepted:

```yaml
# In warp/agents/my_agent/config/my_agent.yml:
model: gpt4
retry: aggressive
conversation: long_context

# In warp/config/app.yml defaults:
defaults:
  model: economic
  retry: low
```
