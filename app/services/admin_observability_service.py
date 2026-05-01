import uuid
from time import perf_counter
from datetime import datetime, timezone
from fastapi import HTTPException, status

from app.config import Settings
from app.models.enums import MemoryType
from app.models.memory_entry import MemoryEntry
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

    def get_decision_conflicts(
        self,
        *,
        project_id: uuid.UUID | None = None,
        limit: int = 20,
        principal: AuthPrincipal | None = None,
    ) -> dict:
        tenant_ids = principal.tenant_ids if principal else None
        items = self.memory_repository.list_decision_conflicts(project_id=project_id, limit=limit, tenant_ids=tenant_ids)
        flattened: list[dict] = []
        for item in items:
            metadata = item.metadata_ or {}
            for conflict in metadata.get("decision_conflicts", []):
                conflicting_id = uuid.UUID(conflict["conflicts_with_entry_id"])
                old_entry = self.memory_repository.get(conflicting_id)
                flattened.append(
                    {
                        "entry_id": item.id,
                        "project_id": item.project_id,
                        "title": item.title,
                        "conflicts_with_entry_id": conflicting_id,
                        "conflicts_with_title": old_entry.title if old_entry else None,
                        "severity": conflict.get("severity", "medium"),
                        "reason": conflict.get("reason", "Decision conflict"),
                        "created_at": item.created_at,
                        "requires_review": bool(metadata.get("requires_review")),
                    }
                )
        flattened.sort(key=lambda row: row["created_at"], reverse=True)
        return {"items": flattened[:limit]}

    def resolve_decision_conflict(
        self,
        *,
        entry_id: uuid.UUID,
        conflicts_with_entry_id: uuid.UUID,
        action: str,
        resolution: str,
        resolved_by: str,
        principal: AuthPrincipal | None = None,
    ) -> dict:
        entry = self.memory_repository.get(entry_id)
        old_entry = self.memory_repository.get(conflicts_with_entry_id)
        if not entry or not old_entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision conflict entry not found")
        if entry.type != MemoryType.decision or old_entry.type != MemoryType.decision:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conflict resolution only supports decisions")
        if principal and principal.tenant_ids is not None:
            allowed = principal.tenant_ids
            if entry.project and entry.project.tenant_id not in allowed:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision conflict entry not found")

        entry_metadata = dict(entry.metadata_ or {})
        old_metadata = dict(old_entry.metadata_ or {})
        now = datetime.now(timezone.utc).isoformat()
        review_record = {
            "action": action,
            "resolution": resolution,
            "resolved_by": resolved_by,
            "resolved_at": now,
            "conflicts_with_entry_id": str(conflicts_with_entry_id),
        }

        if action == "supersede":
            old_metadata["decision_status"] = "superseded"
            old_metadata["deprecated_by_entry_id"] = str(entry_id)
            old_metadata["valid_until"] = now
            old_metadata["review_status"] = "superseded"
            old_metadata["requires_review"] = False
            old_metadata.pop("decision_conflicts", None)

            entry_metadata["decision_status"] = "active"
            entry_metadata["supersedes_entry_id"] = str(conflicts_with_entry_id)
            entry_metadata["valid_from"] = entry_metadata.get("valid_from") or now
            entry_metadata["review_status"] = "approved"
            entry_metadata["requires_review"] = False
            entry_metadata.pop("decision_conflicts", None)
        elif action == "reject_new":
            entry_metadata["decision_status"] = "rejected"
            entry_metadata["review_status"] = "rejected"
            entry_metadata["requires_review"] = False
            entry_metadata.pop("decision_conflicts", None)
            entry.archived = True
        elif action == "keep_both":
            entry_metadata["review_status"] = "approved"
            entry_metadata["requires_review"] = False
            entry_metadata.pop("decision_conflicts", None)
        elif action == "needs_changes":
            entry_metadata["review_status"] = "needs_changes"
            entry_metadata["requires_review"] = True
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown conflict resolution action")

        history = list(entry_metadata.get("review_history", []))
        history.append(review_record)
        entry_metadata["review_history"] = history[-20:]
        entry.metadata_ = entry_metadata
        old_entry.metadata_ = old_metadata

        self.memory_repository.db.add(entry)
        self.memory_repository.db.add(old_entry)
        self.memory_repository.db.flush()
        self.memory_repository.db.refresh(entry)
        self.memory_repository.db.refresh(old_entry)
        return {
            "status": "resolved",
            "action": action,
            "entry_id": entry.id,
            "conflicts_with_entry_id": old_entry.id,
        }

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
