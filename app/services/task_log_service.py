from app.models.task_log import TaskLog
from app.repositories.task_log_repository import TaskLogRepository
from app.schemas.task_logs import TaskLogCreate


class TaskLogService:
    def __init__(self, repository: TaskLogRepository):
        self.repository = repository

    def create_task_log(self, payload: TaskLogCreate) -> TaskLog:
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
            metadata_=payload.metadata,
        )
        return self.repository.create(task_log)

    def import_task_logs(self, payloads: list[TaskLogCreate]) -> int:
        for payload in payloads:
            self.create_task_log(payload)
        return len(payloads)

    def list_task_logs(self, *, agent_id: str | None = None, experiment_id: str | None = None) -> list[TaskLog]:
        return self.repository.list(agent_id=agent_id, experiment_id=experiment_id)

    def get_summary(self, *, agent_id: str | None = None, experiment_id: str | None = None) -> dict:
        return self.repository.summary(agent_id=agent_id, experiment_id=experiment_id)
