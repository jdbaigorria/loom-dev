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


# A model is either a profile name (str) or an inline passthrough config.
ModelConfig = str | CustomModelConfig
