import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MemoryType


class MemoryCreate(BaseModel):
    type: MemoryType
    title: str | None = Field(default=None, max_length=255)
    content: str = Field(min_length=1)
    source_agent: str | None = Field(default=None, max_length=100)
    project_id: uuid.UUID | None = None
    importance: int = Field(default=3, ge=1, le=5)
    metadata: dict = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    content: str | None = None
    source_agent: str | None = Field(default=None, max_length=100)
    project_id: uuid.UUID | None = None
    importance: int | None = Field(default=None, ge=1, le=5)
    archived: bool | None = None
    metadata: dict | None = None


class MemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: MemoryType
    title: str | None
    content: str
    source_agent: str | None
    project_id: uuid.UUID | None
    importance: int
    usage_count: int
    last_used_at: datetime | None
    archived: bool
    metadata: dict = Field(validation_alias="metadata_", serialization_alias="metadata")
    created_at: datetime
    updated_at: datetime


class MemoryArchiveResponse(BaseModel):
    id: uuid.UUID
    archived: bool


class MemoryListResponse(BaseModel):
    items: list[MemoryResponse]


class MemorySearchItem(BaseModel):
    id: uuid.UUID
    type: MemoryType
    title: str | None
    content_preview: str
    score: float
    importance: int
    usage_count: int


class MemorySearchResponse(BaseModel):
    items: list[MemorySearchItem]


class MemoryRelevantRequest(BaseModel):
    query: str = Field(min_length=1)
    project_id: uuid.UUID | None = None
    agent_id: str | None = Field(default=None, max_length=100)
    types: list[MemoryType] | None = None
    limit: int = Field(default=8, ge=1, le=50)
    metadata: dict = Field(default_factory=dict)


class MemoryRelevantItem(BaseModel):
    id: uuid.UUID
    type: MemoryType
    title: str | None
    content: str
    relevance_score: float


class MemoryRelevantResponse(BaseModel):
    context: list[MemoryRelevantItem]
