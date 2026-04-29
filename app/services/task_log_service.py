from app.security import AuthPrincipal, resolve_tenant_for_create
from app.models.task_log import TaskLog
from app.repositories.task_log_repository import TaskLogRepository
from app.schemas.task_logs import TaskLogCreate


class TaskLogService:
    def __init__(self, repository: TaskLogRepository):
        self.repository = repository

    def create_task_log(self, payload: TaskLogCreate, *, principal: AuthPrincipal | None = None) -> TaskLog:
        metadata = dict(payload.metadata)
        if principal and principal.tenant_ids is not None:
            tenant_id = resolve_tenant_for_create(principal, metadata.get("tenant_id"))
            if tenant_id:
                metadata["tenant_id"] = tenant_id
        task_log = TaskLog(
            experiment_id=payload.experiment_id,
            group_name=payload.group_name,
            agent_id=payload.agent_id,
            task_description=payload.task_description,
            used_memory=payload.used_memory,
            memory_entries_count=payload.memory_entries_count,
            duration_seconds=payload.duration_seconds,
            result_quality_score=payload.result_quality_score,
            duplicate_count=payload.duplicate_count,
            consistency_score=payload.consistency_score,
            metadata_=metadata,
        )
        return self.repository.create(task_log)

    def import_task_logs(self, payloads: list[TaskLogCreate], *, principal: AuthPrincipal | None = None) -> int:
        for payload in payloads:
            self.create_task_log(payload, principal=principal)
        return len(payloads)

    def list_task_logs(
        self,
        *,
        agent_id: str | None = None,
        experiment_id: str | None = None,
        principal: AuthPrincipal | None = None,
    ) -> list[TaskLog]:
        tenant_ids = principal.tenant_ids if principal else None
        return self.repository.list(agent_id=agent_id, experiment_id=experiment_id, tenant_ids=tenant_ids)

    def get_summary(
        self,
        *,
        agent_id: str | None = None,
        experiment_id: str | None = None,
        principal: AuthPrincipal | None = None,
    ) -> dict:
        tenant_ids = principal.tenant_ids if principal else None
        return self.repository.summary(agent_id=agent_id, experiment_id=experiment_id, tenant_ids=tenant_ids)
