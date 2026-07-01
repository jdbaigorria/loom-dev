"""
loom.core.loaders.session — Instantiate the session manager for conversation persistence.

Uses a registry (``SESSION_MANAGER_REGISTRY``) to dispatch creation to the
correct constructor based on the ``provider`` configured in ``app.yml``.
Built-in providers: ``file`` (local), ``s3`` (AWS S3). Any other backend plugs
in through the ``custom`` passthrough (dotted ``import_path``), so Loom ships no
adapter for DynamoDB/Redis/etc. — mirroring the model ``custom`` escape hatch.
"""

import logging

from loom.adapters import strands as sx
from loom.adapters.strands import (
    FileSessionManager,
    S3SessionManager,
    SessionManager,
)
from loom.core.exceptions import AgentConfigError
from loom.schemas.config.sessions import CustomSession, SessionConfig

logger = logging.getLogger(__name__)

SESSION_MANAGER_REGISTRY: dict[str, type[SessionManager]] = {
    "file": FileSessionManager,
    "s3": S3SessionManager,
}

#: Per-provider renames from our config field names to the Strands constructor
#: kwargs. Without this the file provider's ``path`` lands in ``**kwargs`` and is
#: silently dropped, so Strands falls back to its ``/tmp/strands/sessions``
#: default and the configured location is ignored.
_CONFIG_KEY_MAP: dict[str, dict[str, str]] = {
    "file": {"path": "storage_dir"},
}


def get_session_manager(session_config: SessionConfig, session_id: str) -> SessionManager:
    """Instantiate the session manager configured in ``app.yml``.

    Args:
        session_config: Session manager configuration with ``provider`` and
            provider-specific parameters.
        session_id: Active session ID. Passed to the manager constructor to
            associate persisted history.

    Returns:
        Strands ``SessionManager`` ready for use with the agent.

    Raises:
        AgentConfigError: If the ``provider`` is not registered, or a ``custom``
            ``import_path`` cannot be resolved.
    """
    if isinstance(session_config, CustomSession):
        return _build_custom_session(session_config, session_id)

    if session_config.provider not in SESSION_MANAGER_REGISTRY:
        raise AgentConfigError(
            f"Invalid session manager type: {session_config.provider}",
            tip=f"Use a valid provider: {list(SESSION_MANAGER_REGISTRY.keys())} or 'custom'.",
        )

    logger.debug(
        "Creating session manager: provider=%s, session_id=%s",
        session_config.provider,
        session_id,
    )

    config = session_config.config.model_dump()
    key_map = _CONFIG_KEY_MAP.get(session_config.provider, {})
    config = {key_map.get(k, k): v for k, v in config.items()}
    return SESSION_MANAGER_REGISTRY[session_config.provider](session_id=session_id, **config)


def _build_custom_session(config: CustomSession, session_id: str) -> SessionManager:
    """Resolve a user-provided ``SessionManager`` subclass and instantiate it.

    The class is imported through the ACL by dotted ``import_path`` and built with
    ``session_id`` plus the free-form ``config`` params. Loom validates nothing
    inside ``config`` — it is passed straight to the constructor.

    Raises:
        AgentConfigError: If ``import_path`` cannot be resolved.
    """
    cls = sx.resolve(config.import_path, optional=True)
    if cls is None:
        raise AgentConfigError(
            f"Could not import session manager class '{config.import_path}'.",
            tip="Check the dotted path and that the package is installed. "
            "Example: my.pkg:DynamoSessionManager.",
        )
    logger.debug(
        "Creating custom session manager: import_path=%s, session_id=%s",
        config.import_path,
        session_id,
    )
    return cls(session_id=session_id, **config.config)
