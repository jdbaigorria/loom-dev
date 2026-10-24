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
from loom.core.exceptions import AgentConfigError, ModelLoadError
from loom.schemas.config.models import CustomModelConfig, FallbackModelConfig, ModelConfig

logger = logging.getLogger(__name__)


def resolve_model_config(
    model: ModelConfig,
) -> CustomModelConfig | FallbackModelConfig | list[str | CustomModelConfig]:
    """Return the concrete config for a profile name, inline model, or fallback.

    Raises:
        ModelLoadError: If a profile name is not defined.
    """
    if isinstance(model, list):
        return model
    if isinstance(model, (CustomModelConfig, FallbackModelConfig)):
        return model
    profiles = get_profiles()
    cfg = profiles.model.get(model)
    if cfg is None:
        raise ModelLoadError(
            message=f"Unknown model profile: '{model}'",
            tip=f"Use one of {list(profiles.model)} or define it in warp/config/profiles.toml.",
        )
    return cfg


def is_router_model(model: ModelConfig) -> bool:
    """True when ``model`` selects more than one candidate."""
    try:
        resolved = resolve_model_config(model)
    except ModelLoadError:
        return False
    return isinstance(resolved, (FallbackModelConfig, list))


def declared_model_id(model: ModelConfig) -> str | None:
    """Best-effort id of the first candidate, for logs before a call runs."""
    resolved = resolve_model_config(model)
    if isinstance(resolved, CustomModelConfig):
        return resolved.model_id
    candidates = resolved if isinstance(resolved, list) else resolved.fallback
    first = candidates[0]
    if isinstance(first, str):
        concrete = resolve_model_config(first)
        return concrete.model_id if isinstance(concrete, CustomModelConfig) else None
    return first.model_id


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


def get_model(model: ModelConfig, overlay: dict[str, Any] | None = None) -> Any:
    """Instantiate the configured model, or a ``ModelRouter`` when several are declared."""
    resolved = resolve_model_config(model)
    if isinstance(resolved, (FallbackModelConfig, list)):
        return _build_router(resolved, overlay)
    logger.debug(
        "Loading model: provider=%s, import_path=%s, model_id=%s",
        resolved.provider,
        resolved.import_path,
        resolved.model_id,
    )
    instance = _build_custom_model(resolved, _shared_overlay(overlay))
    logger.info("Model loaded: %s", resolved.import_path or resolved.provider)
    return instance


def _shared_overlay(overlay: dict[str, Any] | None) -> dict[str, Any] | None:
    if not overlay:
        return None
    shared = {key: value for key, value in overlay.items() if key != "by_candidate"}
    return shared or None


def _candidate_entries(
    resolved: FallbackModelConfig | list[str | CustomModelConfig],
) -> tuple[list[tuple[str, CustomModelConfig]], int | None]:
    if isinstance(resolved, list):
        raw: list[str | CustomModelConfig] = resolved
        max_switches = None
    else:
        raw = list(resolved.fallback)
        max_switches = resolved.max_switches
    if len(raw) < 2:
        raise AgentConfigError("A model fallback needs at least 2 candidates.")
    entries: list[tuple[str, CustomModelConfig]] = []
    for item in raw:
        if isinstance(item, str):
            concrete = resolve_model_config(item)
            if not isinstance(concrete, CustomModelConfig):
                raise AgentConfigError(
                    f"Fallback candidate '{item}' is itself a fallback. Name a single model."
                )
            entries.append((item, concrete))
            continue
        if not item.name:
            raise AgentConfigError(
                "An inline fallback candidate needs a name.",
                tip="Set name: next to provider or import_path.",
            )
        entries.append((item.name, item))
    names = [name for name, _ in entries]
    if len(names) != len(set(names)):
        raise AgentConfigError(f"Fallback candidate names must be unique: {names}")
    ids = [cfg.model_id for _, cfg in entries if cfg.model_id]
    if len(ids) != len(set(ids)):
        raise AgentConfigError(f"Fallback candidates repeat a model_id: {ids}")
    return entries, max_switches


def _build_router(
    resolved: FallbackModelConfig | list[str | CustomModelConfig],
    overlay: dict[str, Any] | None,
) -> Any:
    if sx.ModelRouter is None or sx.RoutingCandidate is None:
        raise AgentConfigError(
            "The installed Strands version cannot route across models.",
            tip="Requiere strands-agents >= 1.52",
        )
    entries, max_switches = _candidate_entries(resolved)
    classes = {resolve_import_path(cfg) for _, cfg in entries}
    by_candidate = (overlay or {}).get("by_candidate") or {}
    shared = _shared_overlay(overlay)
    if len(classes) > 1 and shared and not by_candidate:
        raise AgentConfigError(
            "model_params cannot be applied to fallback candidates of different classes.",
            tip='Pass model_params={"by_candidate": {"name": {...}}} for each candidate.',
        )
    built = []
    for name, cfg in entries:
        candidate_overlay = dict(by_candidate.get(name) or {})
        if len(classes) == 1 and shared:
            candidate_overlay = {**shared, **candidate_overlay}
        model = _build_custom_model(cfg, candidate_overlay or None)
        built.append(sx.RoutingCandidate(model=model, name=name))
    return sx.ModelRouter(built, max_switches=max_switches)
