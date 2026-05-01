import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.memory import SearchScope


class ContextBuildRequest(BaseModel):
    query: str = Field(min_length=1)
    project_id: uuid.UUID | None = None
    agent_id: str | None = Field(default=None, max_length=100)
    scope: SearchScope = "project"
    mode: Literal["lexical", "semantic", "hybrid"] = "hybrid"
    limit: int = Field(default=12, ge=1, le=50)


class ContextEntry(BaseModel):
    id: uuid.UUID
    type: str
    title: str | None
    content: str
    score: float
    importance: int
    project_id: uuid.UUID | None = None


class ContextSummary(BaseModel):
    total_items: int
    decisions: int
    constraints: int
    risks: int
    artifacts: int


class ContextBuckets(BaseModel):
    active_decisions: list[ContextEntry]
    constraints: list[ContextEntry]
    risks: list[ContextEntry]
    artifacts: list[ContextEntry]
    tasks: list[ContextEntry]
    notes: list[ContextEntry]
    other: list[ContextEntry]


class ContextBuildResponse(BaseModel):
    context_version: str
    summary: ContextSummary
    context: ContextBuckets
    agent_instructions: list[str]
