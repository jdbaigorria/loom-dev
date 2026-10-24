"""Prompt configuration for agent YAML.

TODO:
- S3 support: allow passing s3://my-bucket/prompts/expert.md so the prompt can live outside the codebase.
- Amazon Bedrock Prompt Management support: allow passing the ARN of the current prompt version
  arn:aws:bedrock:us-west-2:123:prompt/PROMPT123/DRAFT
"""

from typing import Any

from pydantic import model_validator

from .strict import StrictConfig


class PromptConfig(StrictConfig):
    prompt: str
    context: str | None = None
    variables: dict[str, Any] | None = None
    cache: bool = False
    # Set by ConfigSource hydration: when True, `prompt`/`context` hold literal
    # text (already resolved from a file/dir), so the loader uses them verbatim
    # instead of guessing whether they are a path. Keeps build() off the disk and
    # removes the inline-text-vs-path heuristic ambiguity.
    is_resolved: bool = False

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, v: Any) -> Any:
        if isinstance(v, str):
            return {"prompt": v}

        if isinstance(v, dict):
            # Retrocompat: support old "system_prompt" key from pre-refactor YAML files
            if "system_prompt" in v and "prompt" not in v:
                v["prompt"] = v.pop("system_prompt")
            return v

        return v
