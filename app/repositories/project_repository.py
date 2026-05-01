from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.memory_entry import MemoryEntry
from app.models.project import Project


class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, project: Project) -> Project:
        self.db.add(project)
        self.db.flush()
        self.db.refresh(project)
        return project

    def list(self) -> list[Project]:
        return list(self.db.scalars(select(Project).order_by(Project.created_at.desc())))

    def list_with_entry_counts(self) -> list[tuple[Project, int]]:
        rows = self.db.execute(
            select(Project, func.count(MemoryEntry.id))
            .outerjoin(MemoryEntry, MemoryEntry.project_id == Project.id)
            .group_by(Project.id)
            .order_by(Project.created_at.desc())
        ).all()
        return [(row[0], int(row[1] or 0)) for row in rows]

    def get(self, project_id: uuid.UUID) -> Project | None:
        return self.db.get(Project, project_id)

    def delete(self, project: Project) -> None:
        self.db.delete(project)
