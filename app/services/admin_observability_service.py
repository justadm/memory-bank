import uuid
from datetime import datetime, timezone

from app.config import Settings
from app.repositories.memory_repository import MemoryRepository
from app.repositories.metrics_repository import MetricsRepository


class AdminObservabilityService:
    def __init__(self, repository: MetricsRepository, memory_repository: MemoryRepository, settings: Settings):
        self.repository = repository
        self.memory_repository = memory_repository
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

    def get_import_conflicts(self, *, project_id: uuid.UUID | None = None, limit: int = 20) -> dict:
        items = self.memory_repository.list_import_conflicts(project_id=project_id, limit=limit)
        return {
            "items": [
                {
                    "entry_id": item.id,
                    "project_id": item.project_id,
                    "title": item.title,
                    "type": item.type.value,
                    "created_at": item.created_at,
                    "requires_review": bool(item.metadata_.get("requires_review")),
                    "conflicts": item.metadata_.get("import_conflicts", []),
                }
                for item in items
            ]
        }
