# Models & providers

Loom gives you two ways to configure a model: **profile names** (opinionated presets) and **inline configs** (direct passthrough to any Strands provider). Both work wherever `model:` is accepted — agent YAML and app defaults.

## Built-in profiles

Loom ships three profiles out of the box, all targeting Amazon Bedrock:

| Profile | Model | Use case |
|---|---|---|
| `default` | Claude 3.5 Sonnet v2 (Bedrock) | General purpose |
| `economic` | Claude 3.5 Haiku (Bedrock) | Cost-sensitive, fast |
| `powerful` | Claude 3.5 Sonnet v2 (Bedrock) | Best quality |

```yaml
model: default    # or: economic | powerful
```

## Provider aliases (short form)

Instead of the full dotted `import_path`, use a short `provider:` alias:

```yaml
model:
  provider: openai
  params:
    model_id: gpt-4o
    client_args: { api_key: ${oc.env:OPENAI_API_KEY} }
```

### Built-in aliases

| Alias | Strands class |
|---|---|
| `bedrock` | `strands.models.bedrock.BedrockModel` |
| `openai` | `strands.models.openai.OpenAIModel` |
| `openai_responses` | `strands.models.openai_responses.OpenAIResponsesModel` |
| `anthropic` | `strands.models.anthropic.AnthropicModel` |
| `gemini` | `strands.models.gemini.GeminiModel` |
| `litellm` | `strands.models.litellm.LiteLLMModel` |
| `ollama` | `strands.models.ollama.OllamaModel` |
| `mistral` | `strands.models.mistral.MistralModel` |
| `llamaapi` | `strands.models.llamaapi.LlamaAPIModel` |
| `llamacpp` | `strands.models.llamacpp.LlamaCppModel` |
| `sagemaker` | `strands.models.sagemaker.SageMakerAIModel` |
| `writer` | `strands.models.writer.WriterModel` |

## Inline with full path (escape hatch)

For custom model classes or anything not covered by a built-in alias:

```yaml
model:
  import_path: my.pkg.CustomModel
  params:
    model_id: my-custom-model
    base_url: http://localhost:8000
```

## Provider examples

=== "OpenAI"
    ```yaml
    model:
      provider: openai
      params:
        model_id: gpt-4o
        client_args:
          api_key: ${oc.env:OPENAI_API_KEY}
    ```

=== "Anthropic (direct)"
    ```yaml
    model:
      provider: anthropic
      params:
        model_id: claude-sonnet-5-5
        client_args:
          api_key: ${oc.env:ANTHROPIC_API_KEY}
    ```

=== "Gemini"
    ```yaml
    model:
      provider: gemini
      params:
        model_id: gemini-2.0-flash
        client_args:
          api_key: ${oc.env:GOOGLE_API_KEY}
    ```

=== "Ollama (local)"
    ```yaml
    model:
      provider: ollama
      params:
        model_id: llama3.2
        host: http://localhost:11434
    ```

=== "LiteLLM"
    ```yaml
    model:
      provider: litellm
      params:
        model_id: gpt-4o
    ```

=== "Bedrock (custom model)"
    ```yaml
    model:
      provider: bedrock
      params:
        model_id: anthropic.claude-haiku-5-5
        region_name: us-west-2
    ```

## Custom profiles in profiles.toml

Add named profiles under `warp/config/profiles.toml`. Your values are **deep-merged over the built-ins** — existing built-in profiles are preserved, and you can add new ones or override them:

```toml title="warp/config/profiles.toml"
[model.fast]
import_path = "strands.models.bedrock.BedrockModel"
params = { model_id = "anthropic.claude-haiku-5-5" }

[model.gpt4]
provider = "openai"
params = { model_id = "gpt-4o" }
```

Then any agent can use `model: fast` or `model: gpt4`.

## Fallback across candidates

`model` can list candidates in preference order. Loom builds a Strands `ModelRouter`. A failure the retry does not keep (or a retry budget that runs out) moves to the next candidate. The retry budget is per candidate, so three candidates with `retry: low` (3 attempts) can make up to 9 calls. Prefer a low retry when you declare a fallback.

```yaml
model: [powerful, economic]
```

```yaml
model:
  fallback:
    - powerful
    - name: openai-backup
      provider: openai
      params: { model_id: gpt-4o }
  max_switches: 2
```

The same shape works as a profile:

```toml
[model.resilient]
fallback = ["powerful", "economic"]
max_switches = 2
```

`kind: bidi` does not accept a fallback. A single `model_params` overlay is applied to every candidate only when they are the same model class. Mixed classes need `model_params={"by_candidate": {"openai-backup": {...}}}`.

After a call, response metadata `model_id` is the candidate that answered, and `model_attempts` lists each try.

## Custom provider aliases

Add aliases in `warp/config/profiles.toml` under `[providers]`:

```toml title="warp/config/profiles.toml"
[providers]
my_provider = "my.pkg.CustomModel"
internal_llm = "company.llm.InternalModel"
```

Then use `provider: my_provider` in any agent YAML.

## Retry

Retry config is separate from the model but follows the same profile/inline pattern:

```yaml
retry: low      # built-in: 3 attempts, 1s initial, 60s max
retry: medium   # 4 attempts, 2s initial, 90s max
retry: high     # 5 attempts, 3s initial, 120s max

# Inline:
retry:
  max_attempts: 6
  initial_delay: 2.0
  max_delay: 120.0
```

Custom retry profiles:

```toml title="warp/config/profiles.toml"
[retry.aggressive]
max_attempts = 8
initial_delay = 1
max_delay = 180
```

## Environment variables in params

Loom uses OmegaConf for YAML loading, so environment variables are available with `${oc.env:VAR_NAME}`:

```yaml
model:
  provider: openai
  params:
    model_id: gpt-4o
    client_args:
      api_key: ${oc.env:OPENAI_API_KEY}
      organization: ${oc.env:OPENAI_ORG,null}   # null if not set
```
