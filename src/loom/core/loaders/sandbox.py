"""Build a Strands sandbox. Construction does not start Docker or open SSH."""

from __future__ import annotations

from typing import Any

from loom.adapters import strands as sx
from loom.adapters.strands import capabilities
from loom.core.exceptions import AgentConfigError
from loom.schemas.config.sandbox import SandboxConfig
from loom.utils.loaders import import_class_from_dotted_path

_SSH_KEYS = (
    "host",
    "working_dir",
    "identity_file",
    "port",
    "ssh_options",
    "allow_unknown_hosts",
    "allow_unsafe_ssh_options",
)


def get_sandbox(config: SandboxConfig) -> Any:
    """Return a ``DockerSandbox``, ``SshSandbox``, or a custom sandbox class."""
    if not capabilities.agent_accepts("sandbox"):
        raise AgentConfigError(
            "The installed Strands version does not accept sandbox.",
            tip="Requiere strands-agents >= 1.44",
        )
    params = dict(config.params)
    if config.kind == "docker":
        if sx.DockerSandbox is None:
            raise AgentConfigError("DockerSandbox is not available in this Strands build.")
        return sx.DockerSandbox(
            params["container"],
            working_dir=params.get("working_dir"),
            user=params.get("user"),
        )
    if config.kind == "ssh":
        if sx.SshSandbox is None:
            raise AgentConfigError("SshSandbox is not available in this Strands build.")
        # Omitted flags keep the SDK defaults (host-key checks on, option allowlist on).
        kwargs = {key: params[key] for key in _SSH_KEYS if key in params}
        return sx.SshSandbox(**kwargs)
    if "." in config.kind or ":" in config.kind:
        return import_class_from_dotted_path(config.kind)(**params)
    raise AgentConfigError(
        f"Unknown sandbox '{config.kind}'.",
        tip="Use docker, ssh, or import_path.",
    )
