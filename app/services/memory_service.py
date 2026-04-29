import uuid

from fastapi import HTTPException, status

from app.models.access_log import MemoryAccessLog
from app.models.memory_entry import MemoryEntry
from app.models.memory_link import MemoryLink
from app.models.project import Project
from app.repositories.link_repository import LinkRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.links import LinkCreate
from app.schemas.memory import MemoryCreate, MemoryRelevantRequest, MemoryUpdate
from app.schemas.projects import ProjectCreate, ProjectUpdate
from app.services.graph_service import GraphService
from app.services.search_service import SearchService


class ProjectService:
    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    def create_project(self, payload: ProjectCreate) -> Project:
        project = Project(name=payload.name, description=payload.description, metadata_=payload.metadata)
        return self.repository.create(project)

    def list_projects(self) -> list[Project]:
        return self.repository.list()

    def get_project(self, project_id: uuid.UUID) -> Project:
        project = self.repository.get(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return project

    def update_project(self, project_id: uuid.UUID, payload: ProjectUpdate) -> Project:
        project = self.get_project(project_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            if field == "metadata":
                setattr(project, "metadata_", value)
            else:
                setattr(project, field, value)
        self.repository.db.add(project)
        self.repository.db.flush()
        self.repository.db.refresh(project)
        return project

    def delete_project(self, project_id: uuid.UUID) -> None:
        project = self.get_project(project_id)
        self.repository.delete(project)


class MemoryService:
    def __init__(
        self,
        memory_repository: MemoryRepository,
        project_repository: ProjectRepository,
        link_repository: LinkRepository,
    ):
        self.memory_repository = memory_repository
        self.project_repository = project_repository
        self.link_repository = link_repository
        self.search_service = SearchService(memory_repository)
        self.graph_service = GraphService(link_repository)

    def create_memory(self, payload: MemoryCreate) -> MemoryEntry:
        self._validate_project(payload.project_id)
        entry = MemoryEntry(
            type=payload.type,
            title=payload.title,
            content=payload.content,
            source_agent=payload.source_agent,
            project_id=payload.project_id,
            importance=payload.importance,
            metadata_=payload.metadata,
            search_vector=self._build_search_payload(payload.title, payload.content),
        )
        return self.memory_repository.create(entry)

    def get_memory(self, entry_id: uuid.UUID) -> MemoryEntry:
        entry = self.memory_repository.get(entry_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory entry not found")
        return entry

    def list_memory(
        self, *, project_id: uuid.UUID | None = None, memory_type=None, archived: bool | None = None
    ) -> list[MemoryEntry]:
        return self.memory_repository.list(project_id=project_id, memory_type=memory_type, archived=archived)

    def update_memory(self, entry_id: uuid.UUID, payload: MemoryUpdate) -> MemoryEntry:
        entry = self.get_memory(entry_id)
        data = payload.model_dump(exclude_unset=True)
        if "project_id" in data:
            self._validate_project(data["project_id"])
        for field, value in data.items():
            if field == "metadata":
                setattr(entry, "metadata_", value)
            else:
                setattr(entry, field, value)
        if "title" in data or "content" in data:
            entry.search_vector = self._build_search_payload(entry.title, entry.content)
        self.memory_repository.db.add(entry)
        self.memory_repository.db.flush()
        self.memory_repository.db.refresh(entry)
        return entry

    def archive_memory(self, entry_id: uuid.UUID) -> MemoryEntry:
        entry = self.get_memory(entry_id)
        entry.archived = True
        self.memory_repository.db.add(entry)
        self.memory_repository.db.flush()
        self.memory_repository.db.refresh(entry)
        return entry

    def search_memory(
        self, *, query: str, project_id: uuid.UUID | None = None, limit: int = 10
    ) -> list[tuple[MemoryEntry, float]]:
        return self.search_service.search(query=query, project_id=project_id, limit=limit)

    def get_relevant_memory(self, payload: MemoryRelevantRequest) -> list[tuple[MemoryEntry, float]]:
        results = self.search_service.search(
            query=payload.query,
            project_id=payload.project_id,
            limit=payload.limit,
            types=payload.types,
        )
        for entry, _score in results:
            self.memory_repository.increment_usage(entry)
            self.memory_repository.add_access_log(
                MemoryAccessLog(
                    entry_id=entry.id,
                    agent_id=payload.agent_id,
                    task_context=payload.query,
                    metadata_=payload.metadata,
                )
            )
        return results

    def create_link(self, payload: LinkCreate) -> MemoryLink:
        self.get_memory(payload.from_entry_id)
        self.get_memory(payload.to_entry_id)
        link = MemoryLink(
            from_entry_id=payload.from_entry_id,
            to_entry_id=payload.to_entry_id,
            type=payload.type,
            strength=payload.strength,
            created_by_agent=payload.created_by_agent,
            metadata_=payload.metadata,
        )
        return self.link_repository.create(link)

    def delete_link(self, link_id: uuid.UUID) -> None:
        link = self.link_repository.get(link_id)
        if not link:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory link not found")
        self.link_repository.delete(link)

    def get_links(self, entry_id: uuid.UUID) -> tuple[list[MemoryLink], list[MemoryLink]]:
        self.get_memory(entry_id)
        return self.link_repository.get_for_entry(entry_id)

    def get_graph(self, entry_id: uuid.UUID, depth: int):
        self.get_memory(entry_id)
        return self.graph_service.get_graph(entry_id, depth)

    def archive_stale(self, *, older_than_days: int, max_usage_count: int, max_importance: int) -> list[MemoryEntry]:
        return self.memory_repository.archive_stale(
            older_than_days=older_than_days,
            max_usage_count=max_usage_count,
            max_importance=max_importance,
        )

    def _validate_project(self, project_id: uuid.UUID | None) -> None:
        if project_id and not self.project_repository.get(project_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    @staticmethod
    def _build_search_payload(title: str | None, content: str) -> str:
        # Keep a normalized search payload in the row even when Postgres FTS is not available.
        return " ".join(part.strip() for part in [title or "", content] if part and part.strip())
