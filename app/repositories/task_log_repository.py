from __future__ import annotations

from sqlalchemy import Float, case, cast, func, select
from sqlalchemy.orm import Session

from app.models.task_log import TaskLog


class TaskLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, task_log: TaskLog) -> TaskLog:
        self.db.add(task_log)
        self.db.flush()
        self.db.refresh(task_log)
        return task_log

    def list(
        self,
        *,
        agent_id: str | None = None,
        experiment_id: str | None = None,
        tenant_ids: set[str] | None = None,
    ) -> list[TaskLog]:
        stmt = select(TaskLog).order_by(TaskLog.logged_at.desc())
        if agent_id:
            stmt = stmt.where(TaskLog.agent_id == agent_id)
        if experiment_id:
            stmt = stmt.where(TaskLog.experiment_id == experiment_id)
        stmt = self._apply_tenant_filter(stmt, tenant_ids)
        return list(self.db.scalars(stmt))

    def summary(
        self,
        *,
        agent_id: str | None = None,
        experiment_id: str | None = None,
        tenant_ids: set[str] | None = None,
    ) -> dict:
        stmt = select(
            func.count(TaskLog.id),
            func.avg(case((TaskLog.used_memory.is_(True), 1.0), else_=0.0)),
            func.avg(TaskLog.duration_seconds),
            func.avg(TaskLog.result_quality_score),
            func.avg(TaskLog.consistency_score),
            func.avg(TaskLog.duplicate_count),
        )
        if agent_id:
            stmt = stmt.where(TaskLog.agent_id == agent_id)
        if experiment_id:
            stmt = stmt.where(TaskLog.experiment_id == experiment_id)
        stmt = self._apply_tenant_filter(stmt, tenant_ids)

        total, usage_rate, avg_duration, avg_quality, avg_consistency, avg_duplicate = self.db.execute(stmt).one()
        return {
            "total_tasks": int(total or 0),
            "memory_usage_rate": float(usage_rate or 0.0),
            "avg_duration_seconds": float(avg_duration) if avg_duration is not None else None,
            "avg_quality_score": float(avg_quality) if avg_quality is not None else None,
            "avg_consistency_score": float(avg_consistency) if avg_consistency is not None else None,
            "avg_duplicate_count": float(avg_duplicate) if avg_duplicate is not None else None,
        }

    @staticmethod
    def _apply_tenant_filter(stmt, tenant_ids: set[str] | None):
        if tenant_ids is None:
            return stmt
        return stmt.where(TaskLog.metadata_["tenant_id"].as_string().in_(sorted(tenant_ids)))
