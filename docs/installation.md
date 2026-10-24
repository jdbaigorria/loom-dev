# Installation

## Requirements

- **Python ≥ 3.11** (3.14 recommended for development)
- **uv** or **pip** for package management
- **AWS credentials** with Bedrock access if using the default model (Bedrock). Use `loom doctor` to validate.

## Install from GitHub

Loom isn't published on PyPI yet — install straight from this repo, pinned to a release tag. The distribution name is `loom-declarative`; the import package (`import loom`) and the CLI (`loom`) are unchanged.

Loom splits its dependencies into a slim runtime core and optional extras:

| Extra | Contents | Use when |
|---|---|---|
| *(none)* | Core runtime only | Embedding Loom in your app |
| `[cli]` | CLI, wizards, templates (typer, inquirerpy, jinja2, rich) | Authoring agents |
| `[evals]` | Alias that installs `loom-declarative-evals` | Running evals |
| `[aws]` | `boto3` for `loom doctor --aws` | AWS/Bedrock checks |
| `[all]` | Everything above | Full authoring experience |

Replace `vX.Y.Z` below with a real [release tag](https://github.com/jdbaigorria/loom-dev/tags).

=== "pip"
    ```bash
    # Slim runtime (production deployment):
    pip install "loom-declarative @ git+https://github.com/jdbaigorria/loom-dev@vX.Y.Z"

    # Full authoring experience:
    pip install "loom-declarative[all] @ git+https://github.com/jdbaigorria/loom-dev@vX.Y.Z"

    # Pick extras:
    pip install "loom-declarative[cli] @ git+https://github.com/jdbaigorria/loom-dev@vX.Y.Z"
    ```

=== "uv"
    ```bash
    # As a project dependency:
    uv add "loom-declarative[all] @ git+https://github.com/jdbaigorria/loom-dev@vX.Y.Z"

    # As a standalone CLI tool (no project needed):
    uv tool install "loom-declarative[cli] @ git+https://github.com/jdbaigorria/loom-dev@vX.Y.Z"
    ```

Each tagged release also attaches a pre-built wheel to its [GitHub Release](https://github.com/jdbaigorria/loom-dev/releases) — download it and `pip install path/to/loom_declarative-*.whl` if you'd rather not build from source.

## Install from source (editable)

```bash
git clone https://github.com/jdbaigorria/loom-dev
cd loom-dev
uv sync --all-extras
```

Verify the install:

```bash
loom version
loom doctor --no-aws
```

## Environment check

```bash
loom doctor          # checks Python, loom.toml, AWS credentials + Bedrock access
loom doctor --no-aws # skip AWS/Bedrock checks
```

`loom doctor` requires the `[aws]` extra for the Bedrock checks. The base checks (Python version, project files) run without it.

## AWS / Bedrock setup

The three built-in model profiles (`default`, `economic`, `powerful`) target Amazon Bedrock. You need:

1. AWS credentials — via `~/.aws/credentials`, environment variables (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`), or an IAM role.
2. Model access enabled in the [Amazon Bedrock console](https://console.aws.amazon.com/bedrock/) for `us-east-1` (the default region — configurable in `loom.toml` or `warp/config/app.yml`).

To use a different provider (OpenAI, Anthropic, Gemini, Ollama, ...) see [Models & providers](guides/models.md) — no AWS needed.
