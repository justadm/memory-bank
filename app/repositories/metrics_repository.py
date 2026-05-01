from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Float, case, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models.memory_entry import MemoryEntry
from app.models.memory_link import MemoryLink
from app.models.project import Project
from app.models.task_log import TaskLog


class MetricsRepository:
    def __init__(self, db: Session):
        self.db = db

    def memory_overview(self, *, project_id: uuid.UUID | None = None, tenant_ids: set[str] | None = None) -> dict:
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
        ).select_from(MemoryEntry)
        if tenant_ids is not None:
            stmt = stmt.join(Project, Project.id == MemoryEntry.project_id).where(self._project_tenant_clause(tenant_ids))
        if project_id:
            stmt = stmt.where(MemoryEntry.project_id == project_id)

        total_entries, active_entries, archived_entries, reuse_rate = self.db.execute(stmt).one()

        orphan_stmt = (
            select(func.count(func.distinct(MemoryEntry.id)))
            .select_from(MemoryEntry)
            .outerjoin(MemoryLink, or_(MemoryLink.from_entry_id == MemoryEntry.id, MemoryLink.to_entry_id == MemoryEntry.id))
            .where(MemoryEntry.archived.is_(False), MemoryLink.id.is_(None))
        )
        active_stmt = select(func.count(MemoryEntry.id)).select_from(MemoryEntry).where(MemoryEntry.archived.is_(False))
        if tenant_ids is not None:
            orphan_stmt = orphan_stmt.join(Project, Project.id == MemoryEntry.project_id).where(
                self._project_tenant_clause(tenant_ids)
            )
            active_stmt = active_stmt.join(Project, Project.id == MemoryEntry.project_id).where(
                self._project_tenant_clause(tenant_ids)
            )
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

    def graph_overview(self, *, project_id: uuid.UUID | None = None, tenant_ids: set[str] | None = None) -> dict:
        stmt = select(
            func.count(MemoryLink.id),
            func.avg(MemoryLink.strength),
        )
        if project_id or tenant_ids is not None:
            from_entries = select(MemoryEntry.id).select_from(MemoryEntry)
            to_entries = select(MemoryEntry.id).select_from(MemoryEntry)
            if tenant_ids is not None:
                from_entries = from_entries.join(Project, Project.id == MemoryEntry.project_id).where(
                    self._project_tenant_clause(tenant_ids)
                )
                to_entries = to_entries.join(Project, Project.id == MemoryEntry.project_id).where(
                    self._project_tenant_clause(tenant_ids)
                )
            if project_id:
                from_entries = from_entries.where(MemoryEntry.project_id == project_id)
                to_entries = to_entries.where(MemoryEntry.project_id == project_id)
            stmt = stmt.where(
                MemoryLink.from_entry_id.in_(from_entries),
                MemoryLink.to_entry_id.in_(to_entries),
            )

        total_links, avg_link_strength = self.db.execute(stmt).one()
        return {
            "total_links": int(total_links or 0),
            "avg_link_strength": float(avg_link_strength or 0.0),
        }

    def task_overview(
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
        stmt = self._apply_task_tenant_filter(stmt, tenant_ids)

        total, usage_rate, avg_duration, avg_quality, avg_consistency, avg_duplicate = self.db.execute(stmt).one()
        return {
            "total_tasks": int(total or 0),
            "memory_usage_rate": float(usage_rate or 0.0),
            "avg_duration_seconds": float(avg_duration) if avg_duration is not None else None,
            "avg_quality_score": float(avg_quality) if avg_quality is not None else None,
            "avg_consistency_score": float(avg_consistency) if avg_consistency is not None else None,
            "avg_duplicate_count": float(avg_duplicate) if avg_duplicate is not None else None,
        }

    def task_breakdown_by_field(
        self,
        field_name: str,
        *,
        limit: int = 5,
        tenant_ids: set[str] | None = None,
    ) -> list[dict]:
        field = getattr(TaskLog, field_name)
        stmt = (
            select(
                field.label("key"),
                func.count(TaskLog.id).label("total_tasks"),
                func.avg(case((TaskLog.used_memory.is_(True), 1.0), else_=0.0)).label("memory_usage_rate"),
                func.avg(TaskLog.result_quality_score).label("avg_quality_score"),
                func.avg(TaskLog.consistency_score).label("avg_consistency_score"),
            )
            .where(field.is_not(None))
            .group_by(field)
            .order_by(func.count(TaskLog.id).desc(), field.asc())
            .limit(limit)
        )
        stmt = self._apply_task_tenant_filter(stmt, tenant_ids)
        rows = self.db.execute(stmt).all()
        return [
            {
                "key": row.key,
                "total_tasks": int(row.total_tasks or 0),
                "memory_usage_rate": float(row.memory_usage_rate or 0.0),
                "avg_quality_score": float(row.avg_quality_score) if row.avg_quality_score is not None else None,
                "avg_consistency_score": float(row.avg_consistency_score)
                if row.avg_consistency_score is not None
                else None,
            }
            for row in rows
        ]

    def recent_activity_overview(self, *, window_hours: int = 24, tenant_ids: set[str] | None = None) -> dict:
        threshold = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        memory_stmt = select(func.count(MemoryEntry.id)).select_from(MemoryEntry).where(MemoryEntry.created_at >= threshold)
        if tenant_ids is not None:
            memory_stmt = memory_stmt.join(Project, Project.id == MemoryEntry.project_id).where(
                self._project_tenant_clause(tenant_ids)
            )
        memory_entries_created = int(self.db.scalar(memory_stmt) or 0)

        task_stmt = select(func.count(TaskLog.id)).where(TaskLog.created_at >= threshold)
        task_stmt = self._apply_task_tenant_filter(task_stmt, tenant_ids)
        task_logs_created = int(self.db.scalar(task_stmt) or 0)
        return {
            "window_hours": window_hours,
            "memory_entries_created": memory_entries_created,
            "task_logs_created": task_logs_created,
        }

    def review_overview(self, *, project_id: uuid.UUID | None = None, tenant_ids: set[str] | None = None) -> dict:
        items = self._memory_entries(project_id=project_id, tenant_ids=tenant_ids)
        pending_import_conflicts = 0
        pending_decision_conflicts = 0
        review_overdue = 0
        quality_review_required = 0
        semantic_duplicate_flagged = 0
        false_positive = 0
        approved_review = 0
        archived_after_review = 0
        compaction_summary = 0
        compacted_original = 0
        review_resolved = 0

        for item in items:
            metadata = item.metadata_ or {}
            quality = metadata.get("quality", {}) if isinstance(metadata, dict) else {}
            if metadata.get("requires_review") and metadata.get("import_conflicts"):
                pending_import_conflicts += 1
            if metadata.get("requires_review") and metadata.get("decision_conflicts"):
                pending_decision_conflicts += 1
            if metadata.get("review_overdue") is True:
                review_overdue += 1
            if metadata.get("quality_review_required") is True:
                quality_review_required += 1
            if quality.get("semantic_duplicate_risk") is True:
                semantic_duplicate_flagged += 1
            if quality.get("false_positive") is True:
                false_positive += 1
            if metadata.get("review_status") == "approved":
                approved_review += 1
            if metadata.get("review_status") == "archived" or (
                item.archived and metadata.get("review_history")
            ):
                archived_after_review += 1
            if metadata.get("compaction") is True:
                compaction_summary += 1
            if metadata.get("compacted_into_entry_id"):
                compacted_original += 1
            if metadata.get("review_history"):
                review_resolved += 1

        resolution_rate = review_resolved / max(
            pending_import_conflicts + pending_decision_conflicts + review_overdue + quality_review_required + review_resolved,
            1,
        )
        false_positive_rate = false_positive / max(review_resolved, 1)
        return {
            "pending_import_conflicts_count": pending_import_conflicts,
            "pending_decision_conflicts_count": pending_decision_conflicts,
            "review_overdue_count": review_overdue,
            "quality_review_required_count": quality_review_required,
            "semantic_duplicate_flagged_count": semantic_duplicate_flagged,
            "false_positive_count": false_positive,
            "approved_review_count": approved_review,
            "archived_after_review_count": archived_after_review,
            "compaction_summary_count": compaction_summary,
            "compacted_original_count": compacted_original,
            "review_resolution_rate": float(resolution_rate),
            "false_positive_rate": float(false_positive_rate),
        }

    def trend_overview(self, *, project_id: uuid.UUID | None = None, tenant_ids: set[str] | None = None) -> dict:
        items = self._memory_entries(project_id=project_id, tenant_ids=tenant_ids)
        threshold = datetime.now(timezone.utc) - timedelta(days=7)
        entries_created_7d = 0
        reviews_resolved_7d = 0
        duplicate_flags_7d = 0
        compactions_applied_7d = 0
        for item in items:
            created_at = item.created_at if item.created_at.tzinfo else item.created_at.replace(tzinfo=timezone.utc)
            metadata = item.metadata_ or {}
            quality = metadata.get("quality", {}) if isinstance(metadata, dict) else {}
            if created_at >= threshold:
                entries_created_7d += 1
                if quality.get("semantic_duplicate_risk") is True:
                    duplicate_flags_7d += 1
                if metadata.get("compaction") is True:
                    compactions_applied_7d += 1
            for history_item in metadata.get("review_history", []):
                resolved_at = history_item.get("resolved_at")
                if not resolved_at:
                    continue
                try:
                    resolved_dt = datetime.fromisoformat(resolved_at.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if resolved_dt >= threshold:
                    reviews_resolved_7d += 1
        return {
            "entries_created_7d": entries_created_7d,
            "reviews_resolved_7d": reviews_resolved_7d,
            "duplicate_flags_7d": duplicate_flags_7d,
            "compactions_applied_7d": compactions_applied_7d,
        }

    def _memory_entries(self, *, project_id: uuid.UUID | None = None, tenant_ids: set[str] | None = None) -> list[MemoryEntry]:
        stmt = select(MemoryEntry)
        if project_id:
            stmt = stmt.where(MemoryEntry.project_id == project_id)
        if tenant_ids is not None:
            stmt = stmt.join(Project, Project.id == MemoryEntry.project_id).where(self._project_tenant_clause(tenant_ids))
        return list(self.db.scalars(stmt))

    @staticmethod
    def _project_tenant_clause(tenant_ids: set[str]):
        return Project.metadata_["tenant_id"].as_string().in_(sorted(tenant_ids))

    @staticmethod
    def _apply_task_tenant_filter(stmt, tenant_ids: set[str] | None):
        if tenant_ids is None:
            return stmt
        return stmt.where(TaskLog.metadata_["tenant_id"].as_string().in_(sorted(tenant_ids)))
