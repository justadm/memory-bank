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


class DecisionConflictItemResponse(BaseModel):
    entry_id: uuid.UUID
    project_id: uuid.UUID | None
    title: str | None
    conflicts_with_entry_id: uuid.UUID
    conflicts_with_title: str | None
    severity: str
    reason: str
    created_at: datetime
    requires_review: bool


class DecisionConflictListResponse(BaseModel):
    items: list[DecisionConflictItemResponse]


class DecisionConflictResolutionRequest(BaseModel):
    entry_id: uuid.UUID
    conflicts_with_entry_id: uuid.UUID
    action: str
    resolution: str
    resolved_by: str


class DecisionConflictResolutionResponse(BaseModel):
    status: str
    action: str
    entry_id: uuid.UUID
    conflicts_with_entry_id: uuid.UUID


class ReviewQueueItemResponse(BaseModel):
    entry_id: uuid.UUID
    project_id: uuid.UUID | None
    title: str | None
    type: str
    created_at: datetime
    review_status: str | None = None
    review_overdue: bool = False
    quality_review_required: bool = False


class CompactionCandidateResponse(BaseModel):
    project_id: uuid.UUID | None
    entry_ids: list[uuid.UUID]
    representative_titles: list[str]
    types: dict[str, int]
    suggested_title: str


class ReviewQueuesSummaryResponse(BaseModel):
    import_conflicts_count: int
    decision_conflicts_count: int
    review_overdue_count: int
    quality_review_required_count: int
    compaction_candidate_clusters_count: int
    compaction_candidate_entries_count: int
    review_overdue_items: list[ReviewQueueItemResponse]
    quality_review_required_items: list[ReviewQueueItemResponse]
    compaction_candidates: list[CompactionCandidateResponse]


class QualityReviewResolutionRequest(BaseModel):
    entry_id: uuid.UUID
    action: str
    resolution: str
    resolved_by: str


class QualityReviewResolutionResponse(BaseModel):
    status: str
    action: str
    entry_id: uuid.UUID


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


class ProjectDuplicateGroupItemResponse(BaseModel):
    project_name: str
    source_path: str | None
    project_ids: list[uuid.UUID]
    duplicate_count: int
    total_entries: int
    latest_updated_at: datetime


class ProjectDuplicateSummaryResponse(BaseModel):
    duplicate_groups_count: int
    duplicate_projects_count: int
    items: list[ProjectDuplicateGroupItemResponse]


class RuntimeSelfCheckResponse(BaseModel):
    status: str
    environment: str
    generated_at: datetime
    search_query: str
    project_id: uuid.UUID | None
    health_ok: bool
    projects_read_ok: bool
    search_ok: bool
    projects_count: int
    search_results_count: int
    search_mode: str
    elapsed_ms: float
