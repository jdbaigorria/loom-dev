"""
loom.core.loaders.model — Instantiate the LLM model from configuration.

A model is either a **profile name** (resolved from ``loom.config.profiles``) or an
inline ``CustomModelConfig`` passthrough. Either way it ends up as a dotted
``import_path`` + ``params``, resolved through the ACL — so any Strands ``Model``
(Bedrock, OpenAI, Gemini, LiteLLM, Ollama) or a custom subclass works with one code
path, and Loom maintains no per-provider schema.

A caller may also supply a per-run ``overlay`` of constructor params, merged on top
of the declarative ``params``. This is the build-time sibling of ``extras`` /
``invocation_state``: config stays declarative and cacheable, while secrets and other
per-run values (e.g. a Bedrock ``boto_session`` carrying credentials) are injected by
the caller without touching the ``ConfigSource``.
"""

import logging
from typing import Any

from loom.adapters import strands as sx
from loom.adapters.strands import Model
from loom.config.profiles import get_profiles
from loom.core.exceptions import ModelLoadError
from loom.schemas.config.models import CustomModelConfig, ModelConfig

logger = logging.getLogger(__name__)


def resolve_model_config(model: ModelConfig) -> CustomModelConfig:
    """Return the concrete ``CustomModelConfig`` for a profile name or inline config.

    Raises:
        ModelLoadError: If a profile name is not defined.
    """
    if isinstance(model, str):
        profiles = get_profiles()
        cfg = profiles.model.get(model)
        if cfg is None:
            raise ModelLoadError(
                message=f"Unknown model profile: '{model}'",
                tip=f"Use one of {list(profiles.model)} or define it in warp/config/profiles.toml.",
            )
        return cfg
    return model


def resolve_import_path(config: CustomModelConfig) -> str:
    """Return the dotted ``import_path`` for a config, resolving a ``provider`` alias.

    Raises:
        ModelLoadError: If ``provider`` is not a known alias.
    """
    if config.import_path:
        return config.import_path
    providers = get_profiles().providers
    path = providers.get(config.provider or "")
    if path is None:
        raise ModelLoadError(
            message=f"Unknown model provider: '{config.provider}'",
            tip=(
                f"Use one of {sorted(providers)}, add it under [providers] in "
                "warp/config/profiles.toml, or set import_path directly."
            ),
        )
    return path


def _build_custom_model(config: CustomModelConfig, overlay: dict[str, Any] | None = None) -> Model:
    """Build any Strands ``Model`` by resolving its class through the ACL.

    ``overlay`` (per-run constructor params) is merged on top of the config's
    declarative ``params`` — later keys win — and passed to the model constructor.
    """
    import_path = resolve_import_path(config)
    cls = sx.resolve(import_path, optional=True)
    if cls is None:
        raise ModelLoadError(
            message=f"Could not import model class '{import_path}'.",
            tip=(
                "Check the dotted path and that the package is installed. "
                "Example: strands.models.openai.OpenAIModel "
                "(pip install 'strands-agents[openai]')."
            ),
        )
    params = config.build_model()
    if overlay:
        params = {**params, **overlay}
    # Never log ``params``/``overlay`` — the overlay may carry credentials.
    return cls(**params)


def get_model(model: ModelConfig, overlay: dict[str, Any] | None = None) -> Model:
    """Instantiate the configured model (profile name or inline passthrough).

    Args:
        model: A profile name or an inline ``CustomModelConfig``.
        overlay: Optional per-run constructor params merged on top of the config's
            declarative ``params`` (later keys win). The place to inject per-run
            secrets — e.g. ``{"boto_session": boto3.Session(...)}`` for Bedrock —
            without persisting them in the ``ConfigSource``.

    Returns:
        A ``strands.models.Model`` instance ready for use with ``strands.Agent``.

    Raises:
        ModelLoadError: If the profile is unknown or the ``import_path`` is unresolvable.
    """
    config = resolve_model_config(model)
    logger.debug(
        "Loading model: provider=%s, import_path=%s, model_id=%s",
        config.provider,
        config.import_path,
        config.model_id,
    )
    instance = _build_custom_model(config, overlay)
    logger.info("Model loaded: %s", config.import_path or config.provider)
    return instance
