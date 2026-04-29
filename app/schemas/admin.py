import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.metrics import GraphMetricsResponse, MemoryMetricsResponse, TaskMetricsResponse


class ObservabilityBreakdownItem(BaseModel):
    key: str
    total_tasks: int
    memory_usage_rate: float
    avg_quality_score: float | None
    avg_consistency_score: float | None


class ObservabilityRecentActivityResponse(BaseModel):
    window_hours: int
    memory_entries_created: int
    task_logs_created: int


class ObservabilitySummaryResponse(BaseModel):
    status: str
    environment: str
    generated_at: datetime
    memory: MemoryMetricsResponse
    graph: GraphMetricsResponse
    tasks: TaskMetricsResponse
    recent_activity: ObservabilityRecentActivityResponse
    top_agents: list[ObservabilityBreakdownItem]
    top_experiments: list[ObservabilityBreakdownItem]


class ImportConflictItemResponse(BaseModel):
    entry_id: uuid.UUID
    project_id: uuid.UUID | None
    title: str | None
    type: str
    created_at: datetime
    requires_review: bool
    conflicts: list[dict]


class ImportConflictListResponse(BaseModel):
    items: list[ImportConflictItemResponse]


class ImportProjectSummaryItemResponse(BaseModel):
    project_id: uuid.UUID
    project_name: str
    source_path: str | None
    imported_entries_count: int
    import_events_count: int
    conflicts_detected_count: int
    last_imported_at: datetime | None


class ImportProjectSummaryListResponse(BaseModel):
    items: list[ImportProjectSummaryItemResponse]
