from __future__ import annotations

import uuid

from sqlalchemy import Float, case, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models.memory_entry import MemoryEntry
from app.models.memory_link import MemoryLink
from app.models.task_log import TaskLog


class MetricsRepository:
    def __init__(self, db: Session):
        self.db = db

    def memory_overview(self, *, project_id: uuid.UUID | None = None) -> dict:
        stmt = select(
            func.count(MemoryEntry.id),
            func.count(MemoryEntry.id).filter(MemoryEntry.archived.is_(False)),
            func.count(MemoryEntry.id).filter(MemoryEntry.archived.is_(True)),
            (
                func.count(MemoryEntry.id).filter(
                    MemoryEntry.archived.is_(False),
                    MemoryEntry.usage_count > 0,
                )
                / cast(
                    func.nullif(func.count(MemoryEntry.id).filter(MemoryEntry.archived.is_(False)), 0),
                    Float,
                )
            ),
        )
        if project_id:
            stmt = stmt.where(MemoryEntry.project_id == project_id)

        total_entries, active_entries, archived_entries, reuse_rate = self.db.execute(stmt).one()

        orphan_stmt = (
            select(func.count(func.distinct(MemoryEntry.id)))
            .outerjoin(MemoryLink, or_(MemoryLink.from_entry_id == MemoryEntry.id, MemoryLink.to_entry_id == MemoryEntry.id))
            .where(MemoryEntry.archived.is_(False), MemoryLink.id.is_(None))
        )
        active_stmt = select(func.count(MemoryEntry.id)).where(MemoryEntry.archived.is_(False))
        if project_id:
            orphan_stmt = orphan_stmt.where(MemoryEntry.project_id == project_id)
            active_stmt = active_stmt.where(MemoryEntry.project_id == project_id)

        orphan_count = int(self.db.scalar(orphan_stmt) or 0)
        active_count = int(self.db.scalar(active_stmt) or 0)
        orphan_rate = (orphan_count / active_count) if active_count else 0.0

        return {
            "total_entries": int(total_entries or 0),
            "active_entries": int(active_entries or 0),
            "archived_entries": int(archived_entries or 0),
            "reuse_rate": float(reuse_rate or 0.0),
            "orphan_rate": float(orphan_rate),
        }

    def graph_overview(self, *, project_id: uuid.UUID | None = None) -> dict:
        stmt = select(
            func.count(MemoryLink.id),
            func.avg(MemoryLink.strength),
        )
        if project_id:
            from_entries = select(MemoryEntry.id).where(MemoryEntry.project_id == project_id)
            to_entries = select(MemoryEntry.id).where(MemoryEntry.project_id == project_id)
            stmt = stmt.where(
                MemoryLink.from_entry_id.in_(from_entries),
                MemoryLink.to_entry_id.in_(to_entries),
            )

        total_links, avg_link_strength = self.db.execute(stmt).one()
        return {
            "total_links": int(total_links or 0),
            "avg_link_strength": float(avg_link_strength or 0.0),
        }

    def task_overview(self, *, agent_id: str | None = None, experiment_id: str | None = None) -> dict:
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

        total, usage_rate, avg_duration, avg_quality, avg_consistency, avg_duplicate = self.db.execute(stmt).one()
        return {
            "total_tasks": int(total or 0),
            "memory_usage_rate": float(usage_rate or 0.0),
            "avg_duration_seconds": float(avg_duration) if avg_duration is not None else None,
            "avg_quality_score": float(avg_quality) if avg_quality is not None else None,
            "avg_consistency_score": float(avg_consistency) if avg_consistency is not None else None,
            "avg_duplicate_count": float(avg_duplicate) if avg_duplicate is not None else None,
        }

