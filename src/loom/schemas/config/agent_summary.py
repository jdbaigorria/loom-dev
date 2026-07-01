"""Summary schema used by the ``loom agent list`` command."""

from pydantic import BaseModel


class AgentSummary(BaseModel):
    """Lightweight agent descriptor returned by the listing service."""

    name: str
    description: str = "N/A"
    model: str = "N/A"  # profile name (e.g. "default") or an inline model id
    filename: str = "N/A"
    status: str = "ok"  # Can be "ok", "missing", or "error"
    error_msg: str | None = None
