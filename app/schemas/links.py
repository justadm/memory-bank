import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MemoryLinkType


class LinkCreate(BaseModel):
    from_entry_id: uuid.UUID
    to_entry_id: uuid.UUID
    type: MemoryLinkType
    strength: float = Field(default=1.0, ge=0.0)
    created_by_agent: str | None = Field(default=None, max_length=100)
    metadata: dict = Field(default_factory=dict)


class LinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_entry_id: uuid.UUID
    to_entry_id: uuid.UUID
    type: MemoryLinkType
    strength: float
    created_by_agent: str | None
    metadata: dict = Field(validation_alias="metadata_", serialization_alias="metadata")
    created_at: datetime
    updated_at: datetime


class MemoryLinksResponse(BaseModel):
    outgoing: list[LinkResponse]
    incoming: list[LinkResponse]


class GraphNode(BaseModel):
    id: uuid.UUID
    type: str
    title: str | None


class GraphEdge(BaseModel):
    from_: uuid.UUID = Field(alias="from")
    to: uuid.UUID
    type: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
