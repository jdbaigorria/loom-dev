"""Naming rules: agent directory segments and the init workspace directory."""

import re
import unicodedata

from loom.core.exceptions import AgentConfigError


def workspace_dir_name(workspace_name: str | None) -> str:
    """Directory name for ``loom init``, matching the old Jinja path filter.

    ``(workspace_name or "warp").lower().replace(" ", "_")``.
    """
    return (workspace_name or "warp").lower().replace(" ", "_")


def normalize_agent_name(name: str) -> str:
    """Normalize and validate an agent directory name segment.

    Args:
        name: Raw agent name (e.g. from CLI or YAML).

    Returns:
        Normalized name: lowercase, hyphens/spaces → underscores,
        collapsed and stripped.

    Raises:
        AgentConfigError: If the name contains invalid characters or is empty.
    """
    # 1. Minúsculas
    clean = name.lower()

    # 2. Reemplazar guiones y espacios por '_', colapsando múltiple ocurrencias
    clean = re.sub(r"[-\s]+", "_", clean)

    # 3. Eliminar '_' al inicio y final (evita nombres como _mi_agent_ o .hidden)
    clean = clean.strip("_")

    # 4. Eliminar caracteres no ASCII
    clean = re.sub(
        r"[^\x00-\x7F]+",
        "",
        unicodedata.normalize("NFKD", clean).encode("ascii", "ignore").decode(),
    )

    # 5. Validación estricta
    if not clean or not re.fullmatch(r"[a-z0-9_]+", clean):
        raise AgentConfigError(
            f"Invalid agent name '{name}'.",
            tip=(
                "Agent names must contain only letters, numbers, hyphens, and underscores. "
                "Hyphens and spaces are normalized to underscores. "
                "Names cannot be empty or start/end with separators."
            ),
        )
    return clean
