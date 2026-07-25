from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.memory_entry import MemoryEntry
from app.models.project import Project
from app.models.project_connector_identity import ProjectConnectorIdentity


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

    def find_by_name_and_tenant(self, name: str, tenant_id: str | None) -> Project | None:
        projects = self.db.scalars(select(Project).order_by(Project.created_at)).all()
        return next((project for project in projects if project.name == name and project.tenant_id == tenant_id), None)

    def get_connector_identity(
        self,
        *,
        agent: str,
        normalized_tenant_key: str,
        connector_identity: uuid.UUID,
        lock: bool = False,
    ) -> ProjectConnectorIdentity | None:
        statement = select(ProjectConnectorIdentity).where(
            ProjectConnectorIdentity.agent == agent,
            ProjectConnectorIdentity.normalized_tenant_key == normalized_tenant_key,
            ProjectConnectorIdentity.connector_identity == connector_identity,
        )
        if lock:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def has_connector_binding(self, project_id: uuid.UUID) -> bool:
        return self.db.scalar(
            select(ProjectConnectorIdentity.id)
            .where(ProjectConnectorIdentity.project_id == project_id)
            .limit(1)
        ) is not None

    def has_memory_entries(self, project_id: uuid.UUID) -> bool:
        return self.db.scalar(
            select(MemoryEntry.id).where(MemoryEntry.project_id == project_id).limit(1)
        ) is not None

    def delete(self, project: Project) -> None:
        self.db.delete(project)
