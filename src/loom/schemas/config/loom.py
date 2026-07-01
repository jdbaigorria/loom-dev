from pydantic import BaseModel, ConfigDict, Field


class LoomConfig(BaseModel):
    """Project bootstrap config (``loom.toml``): how the filesystem is laid out.

    Intentionally minimal — it locates the workspace, nothing more. Runtime/infra
    settings (region, session, …) belong in ``app.yml`` (``AppConfig``), not here.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    workspace_name: str = Field(default="warp", alias="name")
