# Prompts

The `system_prompt` field in agent YAML accepts three forms: a **file path**, an **inline string**, or a **directory**. Loom resolves the prompt at load time so a missing file fails at startup, not at runtime.

## File path

The most common form. Path is relative to the agent's `config/` directory:

```yaml
system_prompt: prompt.md
```

```markdown title="warp/agents/my_agent/config/prompt.md"
You are a helpful customer support agent for Acme Corp.

Your responsibilities:
- Answer questions about orders, returns, and shipping
- Escalate to a human when the situation requires it

Always be polite, concise, and accurate.
```

## Inline string

For short prompts, embed directly in the YAML:

```yaml
system_prompt: "You are a concise assistant. Answer in one sentence when possible."
```

## Directory (multi-file)

Files in a directory are loaded in alphabetical order and concatenated with a newline separator:

```yaml
system_prompt: prompts/
```

```
warp/agents/my_agent/config/prompts/
├── 01_ROL.md           # Role definition
├── 02_CONTEXTO.md      # Context and background
├── 03_OBJETIVO.md      # Task objective
├── 04_SALIDA.md        # Output format
├── 05_RESTRICCIONES.md # Constraints
└── 06_EJEMPLOS.md      # Few-shot examples
```

This is useful for large, structured prompts where different sections are maintained by different team members or updated independently.

## Variables and context

The `PromptConfig` supports `variables` for template substitution and an optional `context` string:

```yaml
system_prompt:
  prompt: prompt.md
  context: "Additional runtime context injected after the main prompt."
  variables:
    company_name: "Acme Corp"
    language: "English"
  cache: true    # enable prompt caching if supported by the model provider
```

## Prompt caching

Set `cache: true` to enable prompt caching (supported by Anthropic/Claude models with long prompts). This reduces latency and cost when the system prompt is long and repeated across many invocations:

```yaml
system_prompt:
  prompt: prompt.md
  cache: true
```

## Overriding the prompt at runtime

Free-form context (including a prompt override, if a hook is written to honor it) flows into a single invocation as native Strands `invocation_state` — not part of the query text:

```python
agent = build_agent("my_agent", session)
result = agent(
    "...",
    invocation_state={"system_prompt": "You are now a code review assistant."},
)
```

In dev, `run_dev(..., extras={...})` forwards the same dict for you. A hook (or tool, via `tool_context.invocation_state`) reads it — Loom itself does not swap `agent.system_prompt` automatically.

## Prompt file locations

Loom always resolves prompt paths relative to the agent's `config/` directory. You can reference files anywhere in that directory:

```yaml
system_prompt: ../shared_prompts/base.md   # relative path traversal is supported
```

!!! note
    S3 URLs (`s3://...`) and Bedrock Prompt Management ARNs are not yet supported as prompt sources. Validation will flag unsupported prefixes.
