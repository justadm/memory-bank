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


class MetricsOverviewResponse(BaseModel):
    project_id: uuid.UUID | None = None
    agent_id: str | None = None
    experiment_id: str | None = None
    memory: MemoryMetricsResponse
    graph: GraphMetricsResponse
    tasks: TaskMetricsResponse

