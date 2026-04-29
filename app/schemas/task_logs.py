import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskLogCreate(BaseModel):
    experiment_id: str | None = None
    group_name: str | None = None
    agent_id: str | None = None
    task_description: str = Field(min_length=1)
    used_memory: bool = False
    memory_entries_count: int = Field(default=0, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    result_quality_score: float | None = Field(default=None, ge=0, le=1)
    duplicate_count: int = Field(default=0, ge=0)
    consistency_score: float | None = Field(default=None, ge=0, le=1)
    metadata: dict = Field(default_factory=dict)


class TaskLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: str | None
    group_name: str | None
    agent_id: str | None
    task_description: str
    used_memory: bool
    memory_entries_count: int
    duration_seconds: float | None
    result_quality_score: float | None
    duplicate_count: int
    consistency_score: float | None
    logged_at: datetime
    metadata: dict = Field(validation_alias="metadata_", serialization_alias="metadata")
    created_at: datetime
    updated_at: datetime


class TaskLogListResponse(BaseModel):
    items: list[TaskLogResponse]


class TaskLogSummaryResponse(BaseModel):
    total_tasks: int
    memory_usage_rate: float
    avg_duration_seconds: float | None
    avg_quality_score: float | None
    avg_consistency_score: float | None
    avg_duplicate_count: float | None

