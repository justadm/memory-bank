import uuid

from pydantic import BaseModel


class MemoryMetricsResponse(BaseModel):
    total_entries: int
    active_entries: int
    archived_entries: int
    reuse_rate: float
    orphan_rate: float


class GraphMetricsResponse(BaseModel):
    total_links: int
    avg_link_strength: float


class TaskMetricsResponse(BaseModel):
    total_tasks: int
    memory_usage_rate: float
    avg_duration_seconds: float | None
    avg_quality_score: float | None
    avg_consistency_score: float | None
    avg_duplicate_count: float | None


class ReviewMetricsResponse(BaseModel):
    pending_import_conflicts_count: int
    pending_decision_conflicts_count: int
    review_overdue_count: int
    quality_review_required_count: int
    semantic_duplicate_flagged_count: int
    false_positive_count: int
    approved_review_count: int
    archived_after_review_count: int
    compaction_summary_count: int
    compacted_original_count: int
    review_resolution_rate: float
    false_positive_rate: float


class TrendMetricsResponse(BaseModel):
    entries_created_7d: int
    reviews_resolved_7d: int
    duplicate_flags_7d: int
    compactions_applied_7d: int


class MetricsOverviewResponse(BaseModel):
    project_id: uuid.UUID | None = None
    agent_id: str | None = None
    experiment_id: str | None = None
    memory: MemoryMetricsResponse
    graph: GraphMetricsResponse
    tasks: TaskMetricsResponse
    review: ReviewMetricsResponse
    trends: TrendMetricsResponse
