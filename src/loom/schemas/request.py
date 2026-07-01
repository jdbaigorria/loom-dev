"""Request and response schemas for agent invocations."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints


class LocationS3(BaseModel):
    """S3 URI location for a source file."""

    type: Literal["s3"] = "s3"
    uri: str
    bucket_owner: str | None = Field(
        default=None,
        description="The owner of the bucket for cross-account access",
        alias="bucketOwner",
    )


class SourceFileS3(BaseModel):
    """Source file reference backed by an S3 location."""

    location: LocationS3


class ByteSource(BaseModel):
    """Raw bytes or base64-encoded string as a request source."""

    bytes: bytes | str


class AgentComplexRequest(BaseModel):
    """Multimodal request body with a named source attachment."""

    format: str
    name: str
    sources: ByteSource | SourceFileS3


class AgentRequest(BaseModel):
    """Input payload for a single agent invocation."""

    query: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | AgentComplexRequest
    ) = Field(
        ...,
        description="The message or question sent by the frontend, simple string or complex request with sources.",
    )
    session_id: str = Field(
        default="",
        description="Conversation ID. If not sent, a new session is created.",
    )
    user_id: str = Field(
        default="",
        description="User ID. If not sent, an anonymous user is considered.",
    )
    extras: dict[str, Any] = Field(
        default_factory=dict,
        description="Infrastructure context injected by the caller (e.g. JWT claims, tenant, roles). Not sent by the end user.",
    )
