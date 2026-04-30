import uuid
from time import perf_counter
from datetime import datetime, timezone

from app.config import Settings
from app.repositories.memory_repository import MemoryRepository
from app.repositories.metrics_repository import MetricsRepository
from app.security import AuthPrincipal


class AdminObservabilityService:
    def __init__(self, repository: MetricsRepository, memory_repository: MemoryRepository, settings: Settings):
        self.repository = repository
        self.memory_repository = memory_repository
        self.settings = settings

    def get_summary(self, *, principal: AuthPrincipal | None = None) -> dict:
        tenant_ids = principal.tenant_ids if principal else None
        return {
            "status": "ok",
            "environment": self.settings.app_env,
            "generated_at": datetime.now(timezone.utc),
            "memory": self.repository.memory_overview(tenant_ids=tenant_ids),
            "graph": self.repository.graph_overview(tenant_ids=tenant_ids),
            "tasks": self.repository.task_overview(tenant_ids=tenant_ids),
            "recent_activity": self.repository.recent_activity_overview(window_hours=24, tenant_ids=tenant_ids),
            "top_agents": self.repository.task_breakdown_by_field("agent_id", tenant_ids=tenant_ids),
            "top_experiments": self.repository.task_breakdown_by_field("experiment_id", tenant_ids=tenant_ids),
        }

    def get_import_conflicts(
        self,
        *,
        project_id: uuid.UUID | None = None,
        limit: int = 20,
        principal: AuthPrincipal | None = None,
    ) -> dict:
        tenant_ids = principal.tenant_ids if principal else None
        items = self.memory_repository.list_import_conflicts(project_id=project_id, limit=limit, tenant_ids=tenant_ids)
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

    def get_import_summaries(self, *, limit: int = 20, principal: AuthPrincipal | None = None) -> dict:
        tenant_ids = principal.tenant_ids if principal else None
        return {"items": self.memory_repository.list_import_project_summaries(limit=limit, tenant_ids=tenant_ids)}

    def get_runtime_self_check(
        self,
        *,
        search_query: str = "architecture",
        project_id: uuid.UUID | None = None,
        limit: int = 5,
        principal: AuthPrincipal | None = None,
    ) -> dict:
        tenant_ids = principal.tenant_ids if principal else None
        started_at = perf_counter()
        project_summaries = self.memory_repository.list_import_project_summaries(limit=5, tenant_ids=tenant_ids)
        search_matches = self.memory_repository.search(query=search_query, project_id=project_id, limit=limit)
        _elapsed_ms = round((perf_counter() - started_at) * 1000, 2)

        return {
            "status": "ok",
            "environment": self.settings.app_env,
            "generated_at": datetime.now(timezone.utc),
            "search_query": search_query,
            "project_id": project_id,
            "health_ok": True,
            "projects_read_ok": True,
            "search_ok": True,
            "projects_count": len(project_summaries),
            "search_results_count": len(search_matches),
            "search_mode": "lexical",
            "elapsed_ms": _elapsed_ms,
        }
