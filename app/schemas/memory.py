import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import MemoryProvenance, MemoryType

SearchScope = Literal["project", "related", "global"]


class ValidationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "source_inspection",
        "test_run",
        "runtime_health",
        "read_back",
        "external_api_read",
        "human_approval",
    ]
    summary: str = Field(min_length=1, max_length=500)
    captured_at: datetime
    redacted: Literal[True]
    contains_sensitive_data: Literal[False]


class MemoryCreate(BaseModel):
    type: MemoryType
    title: str | None = Field(default=None, max_length=255)
    content: str = Field(min_length=1)
    source_agent: str | None = Field(default=None, max_length=100)
    project_id: uuid.UUID | None = None
    importance: int = Field(default=3, ge=1, le=5)
    metadata: dict = Field(default_factory=dict)
    provenance: MemoryProvenance = MemoryProvenance.unspecified
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    valid_from: datetime | None = None


class MemoryUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    content: str | None = None
    source_agent: str | None = Field(default=None, max_length=100)
    project_id: uuid.UUID | None = None
    importance: int | None = Field(default=None, ge=1, le=5)
    archived: bool | None = None
    metadata: dict | None = None
    provenance: MemoryProvenance | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


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
    provenance: MemoryProvenance
    confidence: float | None
    valid_from: datetime
    valid_to: datetime | None
    history_available: bool
    supersedes_id: uuid.UUID | None
    is_current: bool | None = None
    successor_id: uuid.UUID | None = None
    metadata: dict = Field(validation_alias="metadata_", serialization_alias="metadata")
    created_at: datetime
    updated_at: datetime


class MemoryArchiveResponse(BaseModel):
    id: uuid.UUID
    archived: bool


class MemoryRevisionChanges(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=255)
    content: str | None = Field(default=None, min_length=1)
    source_agent: str | None = Field(default=None, max_length=100)
    importance: int | None = Field(default=None, ge=1, le=5)
    provenance: MemoryProvenance | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def reject_null_content(self) -> "MemoryRevisionChanges":
        if "content" in self.model_fields_set and self.content is None:
            raise ValueError("content cannot be null")
        return self


class MemoryReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: MemoryRevisionChanges = Field(default_factory=MemoryRevisionChanges)
    metadata_patch: dict = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=500)


class MemoryRevisionResponse(BaseModel):
    entry: MemoryResponse
    superseded_id: uuid.UUID
    actor: str
    reason: str
    revised_at: datetime


class MemoryRestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_entry_id: uuid.UUID | None = None
    reason: str = Field(default="restored historical memory", min_length=1, max_length=500)


class MemoryHistoryResponse(BaseModel):
    items: list[MemoryResponse]


class MemoryListResponse(BaseModel):
    items: list[MemoryResponse]


class MemoryChangeEventResponse(BaseModel):
    project_id: uuid.UUID
    sequence: int
    feed_epoch: uuid.UUID
    event_kind: str
    occurred_at: datetime
    entry_id: uuid.UUID
    previous_entry_id: uuid.UUID | None
    restored_from_entry_id: uuid.UUID | None
    actor: str
    reason: str | None


class MemoryChangesResponse(BaseModel):
    items: list[MemoryChangeEventResponse]
    has_more: bool
    next_cursor: str
    committed_high_watermark: int
    feed_epoch: uuid.UUID
    feed_started_at: datetime


class MemorySearchItem(BaseModel):
    id: uuid.UUID
    type: MemoryType
    title: str | None
    project_id: uuid.UUID | None
    project_name: str | None = None
    content_preview: str
    score: float
    lexical_score: float | None = None
    semantic_score: float | None = None
    match_mode: Literal["lexical", "semantic", "hybrid"] = "hybrid"
    importance: int
    usage_count: int


class MemorySearchResponse(BaseModel):
    items: list[MemorySearchItem]


class MemoryRelevantRequest(BaseModel):
    query: str = Field(min_length=1)
    project_id: uuid.UUID | None = None
    agent_id: str | None = Field(default=None, max_length=100)
    types: list[MemoryType] | None = None
    scope: SearchScope = "project"
    search_mode: Literal["lexical", "semantic", "hybrid"] = "hybrid"
    limit: int = Field(default=8, ge=1, le=50)
    metadata: dict = Field(default_factory=dict)
    as_of: datetime | None = None


class MemoryRelevantItem(BaseModel):
    id: uuid.UUID
    type: MemoryType
    title: str | None
    project_id: uuid.UUID | None
    project_name: str | None = None
    content: str
    relevance_score: float


class MemoryRelevantResponse(BaseModel):
    context: list[MemoryRelevantItem]
