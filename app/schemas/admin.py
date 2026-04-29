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
