import uuid

from app.repositories.metrics_repository import MetricsRepository


class MetricsService:
    def __init__(self, repository: MetricsRepository):
        self.repository = repository

    def get_overview(
        self,
        *,
        project_id: uuid.UUID | None = None,
        agent_id: str | None = None,
        experiment_id: str | None = None,
    ) -> dict:
        return {
            "project_id": project_id,
            "agent_id": agent_id,
            "experiment_id": experiment_id,
            "memory": self.repository.memory_overview(project_id=project_id),
            "graph": self.repository.graph_overview(project_id=project_id),
            "tasks": self.repository.task_overview(agent_id=agent_id, experiment_id=experiment_id),
        }

