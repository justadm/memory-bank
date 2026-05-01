import uuid

from app.repositories.metrics_repository import MetricsRepository
from app.security import AuthPrincipal


class MetricsService:
    def __init__(self, repository: MetricsRepository):
        self.repository = repository

    def get_overview(
        self,
        *,
        project_id: uuid.UUID | None = None,
        agent_id: str | None = None,
        experiment_id: str | None = None,
        principal: AuthPrincipal | None = None,
    ) -> dict:
        tenant_ids = principal.tenant_ids if principal else None
        return {
            "project_id": project_id,
            "agent_id": agent_id,
            "experiment_id": experiment_id,
            "memory": self.repository.memory_overview(project_id=project_id, tenant_ids=tenant_ids),
            "graph": self.repository.graph_overview(project_id=project_id, tenant_ids=tenant_ids),
            "tasks": self.repository.task_overview(agent_id=agent_id, experiment_id=experiment_id, tenant_ids=tenant_ids),
            "review": self.repository.review_overview(project_id=project_id, tenant_ids=tenant_ids),
            "trends": self.repository.trend_overview(project_id=project_id, tenant_ids=tenant_ids),
        }
