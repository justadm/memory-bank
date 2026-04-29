import re
import uuid
from copy import deepcopy

from fastapi import HTTPException, status

from app.models.project import Project
from app.repositories.link_repository import LinkRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.imports import ProjectImportRequest
from app.schemas.links import LinkCreate
from app.schemas.memory import MemoryCreate
from app.schemas.projects import ProjectCreate
from app.services.memory_service import MemoryService, ProjectService


SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(token\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(password\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(secret\s*[:=]\s*)([^\s,;]+)"),
]


class ImportService:
    def __init__(
        self,
        memory_repository: MemoryRepository,
        project_repository: ProjectRepository,
        link_repository: LinkRepository,
    ):
        self.memory_service = MemoryService(memory_repository, project_repository, link_repository)
        self.project_service = ProjectService(project_repository)
        self.project_repository = project_repository

    def import_project_scan(self, payload: ProjectImportRequest) -> dict:
        project = self._resolve_project(payload.project, payload.project_id)
        import_event = self.memory_service.create_memory(
            MemoryCreate(
                type="event",
                title=self._mask_text(payload.import_event.title),
                content=self._mask_text(payload.import_event.content),
                source_agent=payload.import_event.source_agent,
                project_id=project.id,
                importance=payload.import_event.importance,
                metadata=self._mask_metadata(payload.import_event.metadata),
            )
        )

        entry_refs: dict[str, uuid.UUID] = {}
        for item in payload.entries:
            if item.ref in entry_refs:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate entry ref: {item.ref}",
                )
            created = self.memory_service.create_memory(
                MemoryCreate(
                    type=item.type,
                    title=self._mask_text(item.title),
                    content=self._mask_text(item.content),
                    source_agent=item.source_agent,
                    project_id=project.id,
                    importance=item.importance,
                    metadata=self._mask_metadata(item.metadata),
                )
            )
            entry_refs[item.ref] = created.id

        created_links = 0
        for item in payload.links:
            from_entry_id = entry_refs.get(item.from_ref)
            to_entry_id = entry_refs.get(item.to_ref)
            if not from_entry_id or not to_entry_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Link references unknown refs: {item.from_ref} -> {item.to_ref}",
                )
            self.memory_service.create_link(
                LinkCreate(
                    from_entry_id=from_entry_id,
                    to_entry_id=to_entry_id,
                    type=item.type,
                    strength=item.strength,
                    created_by_agent=item.created_by_agent,
                    metadata=self._mask_metadata(item.metadata),
                )
            )
            created_links += 1

        return {
            "project": project,
            "import_event_id": import_event.id,
            "entries_created": len(entry_refs),
            "links_created": created_links,
            "entry_refs": entry_refs,
        }

    def _resolve_project(self, project_payload: ProjectCreate | None, project_id: uuid.UUID | None) -> Project:
        if project_payload:
            return self.project_service.create_project(project_payload)
        project = self.project_repository.get(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return project

    def _mask_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        masked = value
        for pattern in SECRET_PATTERNS:
            masked = pattern.sub(r"\1[REDACTED]", masked)
        return masked

    def _mask_metadata(self, metadata: dict) -> dict:
        masked = deepcopy(metadata)
        for key, value in list(masked.items()):
            if isinstance(value, str):
                masked[key] = self._mask_text(value)
            elif isinstance(value, dict):
                masked[key] = self._mask_metadata(value)
            elif isinstance(value, list):
                masked[key] = [self._mask_text(item) if isinstance(item, str) else item for item in value]
        return masked
