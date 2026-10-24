"""Model configuration: a profile name or an inline passthrough.

Loom no longer maintains a typed schema per provider. A model is declared either
as a **profile name** (resolved from ``loom.config.profiles`` — built-ins plus
``warp/config/profiles.toml``) or **inline** as a generic passthrough to any Strands
``Model`` (or a custom subclass). Inline you name the class with either a short
``provider`` alias (resolved to a dotted path through ``loom.config.profiles`` —
built-ins plus ``[providers]`` in ``warp/config/profiles.toml``) or a full dotted
``import_path`` escape hatch. Constructor ``params`` flow through untouched.

    model: economic                          # profile name

    model:                                   # inline, provider alias
      provider: openai
      params: { model_id: gpt-4o }

    model:                                   # inline, explicit dotted path
      import_path: my.pkg.CustomModel
      params: { model_id: gpt-4o }
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CustomModelConfig(BaseModel):
    """Inline passthrough to any Strands ``Model`` (or a user-supplied one).

    Exactly one of ``provider`` (short alias) or ``import_path`` (dotted path)
    must be given. ``provider`` is resolved to an ``import_path`` at load time.
    """

    model_config = ConfigDict(extra="forbid")
    provider: str | None = Field(
        default=None,
        description="Short provider alias resolved to an import_path, e.g. openai, bedrock.",
    )
    import_path: str | None = Field(
        default=None,
        description="Dotted path to a Strands Model class, e.g. strands.models.openai.OpenAIModel",
    )
    params: dict[str, Any] = Field(default_factory=dict)
    name: str | None = Field(
        default=None,
        description="Candidate name when this model is one entry of a fallback list.",
    )

    @model_validator(mode="after")
    def _require_exactly_one_target(self) -> "CustomModelConfig":
        if not self.provider and not self.import_path:
            raise ValueError("Specify either 'provider' or 'import_path'.")
        if self.provider and self.import_path:
            raise ValueError("Specify only one of 'provider' or 'import_path', not both.")
        return self

    @property
    def model_id(self) -> str | None:
        """Best-effort model id (read from params) for metrics/logging uniformity."""
        value = self.params.get("model_id")
        return value if isinstance(value, str) else None

    def build_model(self) -> dict[str, Any]:
        return dict(self.params)


class FallbackModelConfig(BaseModel):
    """Ordered failover across two or more model candidates."""

    model_config = ConfigDict(extra="forbid")
    fallback: list[str | CustomModelConfig] = Field(min_length=2)
    max_switches: int | None = Field(default=None, ge=0)


# A model is a profile name, an inline passthrough, an ordered fallback, or a
# short list of candidates (the same thing as ``fallback`` without a cap).
ModelConfig = str | CustomModelConfig | FallbackModelConfig | list[str | CustomModelConfig]
