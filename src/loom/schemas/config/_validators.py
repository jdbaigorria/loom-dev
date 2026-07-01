from typing import Any


def parse_single_key_dict(data: dict, entry_type: str) -> tuple[str, dict[str, Any]]:
    """Validate and unpack a single-key dict into (name, params).

    Expects a dict with exactly one key whose value is either a mapping or None.
    Used by ToolConfig and HookConfig model validators to parse YAML entries like::

        - my_tool:
            param_a: value

    Args:
        data: Dict to parse. Must have exactly one key.
        entry_type: Label used in error messages (e.g. "Tool", "Hook").

    Returns:
        Tuple of (name, params) where params is always a dict (never None).

    Raises:
        ValueError: If dict is empty, has more than one key, or params is not a mapping.
    """
    if not data:
        raise ValueError(f"{entry_type} entry cannot be an empty dict.")
    if len(data) > 1:
        raise ValueError(f"{entry_type} entry must have exactly one key, got: {list(data.keys())}")
    name = next(iter(data))
    params = data[name]
    if params is not None and not isinstance(params, dict):
        raise ValueError(
            f"{entry_type} params for '{name}' must be a mapping, got {type(params).__name__}."
        )
    return name, params or {}
