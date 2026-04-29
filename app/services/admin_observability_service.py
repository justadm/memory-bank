from datetime import datetime, timezone

from app.config import Settings
from app.repositories.metrics_repository import MetricsRepository


class AdminObservabilityService:
    def __init__(self, repository: MetricsRepository, settings: Settings):
        self.repository = repository
        self.settings = settings

    def get_summary(self) -> dict:
        return {
            "status": "ok",
            "environment": self.settings.app_env,
            "generated_at": datetime.now(timezone.utc),
            "memory": self.repository.memory_overview(),
            "graph": self.repository.graph_overview(),
            "tasks": self.repository.task_overview(),
            "recent_activity": self.repository.recent_activity_overview(window_hours=24),
            "top_agents": self.repository.task_breakdown_by_field("agent_id"),
            "top_experiments": self.repository.task_breakdown_by_field("experiment_id"),
        }
