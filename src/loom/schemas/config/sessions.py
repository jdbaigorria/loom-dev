"""Session storage backend schemas."""

from typing import Annotated, Any, Literal

from pydantic import Field

from .strict import StrictConfig


class S3Config(StrictConfig):
    """Connection parameters for an S3-backed session store."""

    bucket: str
    prefix: str


class FileConfig(StrictConfig):
    """Connection parameters for a file-backed session store."""

    path: str


class S3Session(StrictConfig):
    """Session configuration that persists conversations to S3."""

    provider: Literal["s3"] = "s3"
    config: S3Config


class FileSession(StrictConfig):
    """Session configuration that persists conversations to the local filesystem."""

    provider: Literal["file"] = "file"
    config: FileConfig


class CustomSession(StrictConfig):
    """Session backed by a user-provided ``SessionManager`` subclass.

    Loom ships only ``file`` and ``s3``; any other backend (DynamoDB, Redis, …)
    plugs in here by dotted ``import_path``, mirroring the model ``custom``
    passthrough. The resolved class is constructed with the active ``session_id``
    plus every key in ``config`` as a keyword argument — Loom validates nothing
    inside ``config`` and ships no adapter of its own.
    """

    provider: Literal["custom"] = "custom"
    import_path: str = Field(
        description="Dotted path to a strands SessionManager subclass, e.g. 'my.pkg:DynamoSession'.",
    )
    config: dict[str, Any] = Field(default_factory=dict)


SessionConfig = Annotated[
    S3Session | FileSession | CustomSession, Field(discriminator="provider")
]
