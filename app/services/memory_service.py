import uuid
from pathlib import Path

from fastapi import HTTPException, status

from app.config import get_settings
from app.models.access_log import MemoryAccessLog
from app.models.memory_entry import MemoryEntry
from app.models.memory_link import MemoryLink
from app.models.project import Project
from app.repositories.link_repository import LinkRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.project_repository import ProjectRepository
from app.security import AuthPrincipal, ensure_tenant_access, resolve_tenant_for_create
from app.schemas.links import LinkCreate
from app.schemas.memory import MemoryCreate, MemoryRelevantRequest, MemoryUpdate
from app.schemas.projects import ProjectCreate, ProjectUpdate
from app.services.auto_link_service import AutoLinkService
from app.services.decision_authority_service import DecisionAuthorityService
from app.services.graph_service import GraphService
from app.services.memory_quality_service import MemoryQualityService
from app.services.search_service import SearchService


class ProjectService:
    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    def create_project(self, payload: ProjectCreate, *, principal: AuthPrincipal | None = None) -> Project:
        metadata = dict(payload.metadata)
        tenant_id = resolve_tenant_for_create(principal, payload.tenant_id) if principal else payload.tenant_id
        if tenant_id:
            metadata["tenant_id"] = tenant_id
        project = Project(name=payload.name, description=payload.description, metadata_=metadata)
        return self.repository.create(project)

    def list_projects(self, *, principal: AuthPrincipal | None = None) -> list[Project]:
        items = self.repository.list()
        return [item for item in items if self._can_access_project(item, principal)]

    def get_project(self, project_id: uuid.UUID, *, principal: AuthPrincipal | None = None) -> Project:
        project = self.repository.get(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        self._ensure_project_access(project, principal)
        return project

    def update_project(self, project_id: uuid.UUID, payload: ProjectUpdate, *, principal: AuthPrincipal | None = None) -> Project:
        project = self.get_project(project_id, principal=principal)
        data = payload.model_dump(exclude_unset=True)
        tenant_value = data.pop("tenant_id", None) if "tenant_id" in data else None
        metadata_value = data.pop("metadata", None) if "metadata" in data else None

        for field, value in data.items():
            setattr(project, field, value)

        if "tenant_id" in payload.model_fields_set or "metadata" in payload.model_fields_set:
            metadata = dict(project.metadata_ or {})
            if metadata_value is not None:
                metadata.update(metadata_value)
            if "tenant_id" in payload.model_fields_set:
                tenant_id = resolve_tenant_for_create(principal, tenant_value) if principal else tenant_value
                if tenant_id:
                    metadata["tenant_id"] = tenant_id
                else:
                    metadata.pop("tenant_id", None)
            setattr(project, "metadata_", metadata)
        self.repository.db.add(project)
        self.repository.db.flush()
        self.repository.db.refresh(project)
        return project

    def delete_project(self, project_id: uuid.UUID, *, principal: AuthPrincipal | None = None) -> None:
        project = self.get_project(project_id, principal=principal)
        self.repository.delete(project)

    @staticmethod
    def _ensure_project_access(project: Project, principal: AuthPrincipal | None) -> None:
        if principal is None:
            return
        ensure_tenant_access(principal, project.tenant_id)

    @staticmethod
    def _can_access_project(project: Project, principal: AuthPrincipal | None) -> bool:
        if principal is None or principal.tenant_ids is None:
            return True
        return project.tenant_id in principal.tenant_ids


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
        self.settings = get_settings()
        self.search_service = SearchService(memory_repository)
        self.graph_service = GraphService(link_repository)
        self.quality_service = MemoryQualityService(memory_repository)
        self.decision_authority_service = DecisionAuthorityService(memory_repository)
        self.auto_link_service = AutoLinkService(
            memory_repository=memory_repository,
            link_repository=link_repository,
            settings=self.settings,
        )

    def create_memory(
        self,
        payload: MemoryCreate,
        *,
        principal: AuthPrincipal | None = None,
        enforce_quality_gate: bool = True,
    ) -> MemoryEntry:
        self._validate_project(payload.project_id, principal=principal, require_for_restricted=principal is not None)
        quality = self.quality_service.assess(
            memory_type=payload.type,
            title=payload.title,
            content=payload.content,
            metadata=payload.metadata,
            project_id=payload.project_id,
        )
        metadata = dict(payload.metadata)
        metadata["quality"] = quality.as_metadata()
        if quality.review_required:
            metadata["quality_review_required"] = True
        metadata = self.decision_authority_service.enrich_metadata(
            entry_id=None,
            memory_type=payload.type,
            project_id=payload.project_id,
            title=payload.title,
            content=payload.content,
            metadata=metadata,
        )
        if quality.reject and enforce_quality_gate:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message": "Memory entry did not pass quality validation", "quality": quality.as_metadata()},
            )
        entry = MemoryEntry(
            type=payload.type,
            title=payload.title,
            content=payload.content,
            source_agent=payload.source_agent,
            project_id=payload.project_id,
            importance=payload.importance,
            metadata_=metadata,
            search_vector=None if self.memory_repository.is_postgresql() else self._build_search_payload(payload.title, payload.content),
        )
        created = self.memory_repository.create(entry)
        self.memory_repository.sync_search_vector(created, self._build_search_payload(created.title, created.content))
        self.auto_link_service.link_entry(created)
        return created

    def get_memory(self, entry_id: uuid.UUID, *, principal: AuthPrincipal | None = None) -> MemoryEntry:
        entry = self.memory_repository.get(entry_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory entry not found")
        self._ensure_entry_access(entry, principal)
        return entry

    def list_memory(
        self,
        *,
        project_id: uuid.UUID | None = None,
        memory_type=None,
        archived: bool | None = None,
        principal: AuthPrincipal | None = None,
    ) -> list[MemoryEntry]:
        if project_id:
            self._validate_project(project_id, principal=principal, require_for_restricted=False)
        items = self.memory_repository.list(project_id=project_id, memory_type=memory_type, archived=archived)
        return [item for item in items if self._can_access_entry(item, principal)]

    def update_memory(
        self,
        entry_id: uuid.UUID,
        payload: MemoryUpdate,
        *,
        principal: AuthPrincipal | None = None,
        enforce_quality_gate: bool = True,
    ) -> MemoryEntry:
        entry = self.get_memory(entry_id, principal=principal)
        data = payload.model_dump(exclude_unset=True)
        if "project_id" in data:
            self._validate_project(data["project_id"], principal=principal, require_for_restricted=principal is not None)
        for field, value in data.items():
            if field == "metadata":
                setattr(entry, "metadata_", value)
            else:
                setattr(entry, field, value)
        quality = self.quality_service.assess(
            memory_type=entry.type,
            title=entry.title,
            content=entry.content,
            metadata=entry.metadata_,
            project_id=entry.project_id,
            existing_entry_id=entry.id,
        )
        metadata = dict(entry.metadata_ or {})
        metadata["quality"] = quality.as_metadata()
        if quality.review_required:
            metadata["quality_review_required"] = True
        else:
            metadata.pop("quality_review_required", None)
        metadata = self.decision_authority_service.enrich_metadata(
            entry_id=entry.id,
            memory_type=entry.type,
            project_id=entry.project_id,
            title=entry.title,
            content=entry.content,
            metadata=metadata,
        )
        if quality.reject and enforce_quality_gate:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message": "Memory entry did not pass quality validation", "quality": quality.as_metadata()},
            )
        entry.metadata_ = metadata
        if "title" in data or "content" in data:
            entry.search_vector = None if self.memory_repository.is_postgresql() else self._build_search_payload(entry.title, entry.content)
        self.memory_repository.db.add(entry)
        self.memory_repository.db.flush()
        self.memory_repository.db.refresh(entry)
        self.memory_repository.sync_search_vector(entry, self._build_search_payload(entry.title, entry.content))
        return entry

    def archive_memory(self, entry_id: uuid.UUID, *, principal: AuthPrincipal | None = None) -> MemoryEntry:
        entry = self.get_memory(entry_id, principal=principal)
        entry.archived = True
        self.memory_repository.db.add(entry)
        self.memory_repository.db.flush()
        self.memory_repository.db.refresh(entry)
        return entry

    def search_memory(
        self,
        *,
        query: str,
        project_id: uuid.UUID | None = None,
        scope: str = "project",
        limit: int = 10,
        mode: str = "hybrid",
        principal: AuthPrincipal | None = None,
    ):
        project_ids = self._resolve_scope_project_ids(project_id, scope=scope, principal=principal)
        results = self.search_service.search(
            query=query,
            project_id=None if project_ids else project_id,
            project_ids=project_ids,
            limit=limit,
            mode=mode,
        )
        return [match for match in results if self._can_access_entry(match.entry, principal)]

    def get_relevant_memory(self, payload: MemoryRelevantRequest, *, principal: AuthPrincipal | None = None) -> list[tuple[MemoryEntry, float]]:
        project_ids = self._resolve_scope_project_ids(payload.project_id, scope=payload.scope, principal=principal)
        results = self.search_service.search(
            query=payload.query,
            project_id=None if project_ids else payload.project_id,
            project_ids=project_ids,
            limit=payload.limit,
            types=payload.types,
            mode=payload.search_mode,
        )
        filtered_results = [match for match in results if self._can_access_entry(match.entry, principal)]
        for match in filtered_results:
            self.memory_repository.increment_usage(match.entry)
            self.memory_repository.add_access_log(
                MemoryAccessLog(
                    entry_id=match.entry.id,
                    agent_id=payload.agent_id,
                    task_context=payload.query,
                    metadata_=payload.metadata,
                )
            )
        return [(match.entry, match.score) for match in filtered_results]

    def create_link(self, payload: LinkCreate, *, principal: AuthPrincipal | None = None) -> MemoryLink:
        self.get_memory(payload.from_entry_id, principal=principal)
        self.get_memory(payload.to_entry_id, principal=principal)
        link = MemoryLink(
            from_entry_id=payload.from_entry_id,
            to_entry_id=payload.to_entry_id,
            type=payload.type,
            strength=payload.strength,
            created_by_agent=payload.created_by_agent,
            metadata_=payload.metadata,
        )
        return self.link_repository.create(link)

    def delete_link(self, link_id: uuid.UUID, *, principal: AuthPrincipal | None = None) -> None:
        link = self.link_repository.get(link_id)
        if not link:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory link not found")
        self.get_memory(link.from_entry_id, principal=principal)
        self.get_memory(link.to_entry_id, principal=principal)
        self.link_repository.delete(link)

    def get_links(self, entry_id: uuid.UUID, *, principal: AuthPrincipal | None = None) -> tuple[list[MemoryLink], list[MemoryLink]]:
        self.get_memory(entry_id, principal=principal)
        return self.link_repository.get_for_entry(entry_id)

    def get_graph(self, entry_id: uuid.UUID, depth: int, *, principal: AuthPrincipal | None = None):
        self.get_memory(entry_id, principal=principal)
        nodes, edges = self.graph_service.get_graph(entry_id, depth)
        filtered_nodes = [node for node in nodes if self._can_access_entry(node, principal)]
        allowed_ids = {node.id for node in filtered_nodes}
        filtered_edges = [edge for edge in edges if edge.from_entry_id in allowed_ids and edge.to_entry_id in allowed_ids]
        return filtered_nodes, filtered_edges

    def archive_stale(self, *, older_than_days: int, max_usage_count: int, max_importance: int) -> list[MemoryEntry]:
        return self.memory_repository.archive_stale(
            older_than_days=older_than_days,
            max_usage_count=max_usage_count,
            max_importance=max_importance,
        )

    def rebuild_search_vectors(self, *, project_id: uuid.UUID | None = None) -> int:
        return self.memory_repository.rebuild_search_vectors(project_id=project_id)

    def _validate_project(
        self,
        project_id: uuid.UUID | None,
        *,
        principal: AuthPrincipal | None = None,
        require_for_restricted: bool = False,
    ) -> None:
        if project_id is None:
            if principal and principal.tenant_ids is not None and require_for_restricted:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project_id is required for this principal")
            return
        project = self.project_repository.get(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        if principal:
            ensure_tenant_access(principal, project.tenant_id)

    def _resolve_scope_project_ids(
        self,
        project_id: uuid.UUID | None,
        *,
        scope: str,
        principal: AuthPrincipal | None = None,
    ) -> list[uuid.UUID] | None:
        if scope == "global":
            return None
        if project_id is None:
            return None

        project = self.project_repository.get(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        if principal:
            ensure_tenant_access(principal, project.tenant_id)

        if scope != "related":
            return [project.id]

        related_ids = [project.id]
        related_paths = self._normalize_related_paths(project)
        if not related_paths:
            return related_ids

        for candidate in self.project_repository.list():
            if candidate.id == project.id:
                continue
            if principal and not ProjectService._can_access_project(candidate, principal):
                continue
            candidate_source = self._normalize_source_path(candidate)
            if candidate_source and candidate_source in related_paths:
                related_ids.append(candidate.id)
        return related_ids

    @staticmethod
    def _normalize_source_path(project: Project) -> str | None:
        if not isinstance(project.metadata_, dict):
            return None
        source_path = project.metadata_.get("source_path")
        if not source_path:
            return None
        try:
            return str(Path(str(source_path)).expanduser().resolve())
        except OSError:
            return str(source_path)

    def _normalize_related_paths(self, project: Project) -> set[str]:
        if not isinstance(project.metadata_, dict):
            return set()
        related_projects = project.metadata_.get("related_projects", [])
        if not isinstance(related_projects, list):
            return set()

        normalized: set[str] = set()
        for item in related_projects:
            if not item:
                continue
            try:
                normalized.add(str(Path(str(item)).expanduser().resolve()))
            except OSError:
                normalized.add(str(item))
        return normalized

    def _can_access_entry(self, entry: MemoryEntry, principal: AuthPrincipal | None) -> bool:
        if principal is None or principal.tenant_ids is None:
            return True
        if entry.project_id is None:
            return False
        project = self.project_repository.get(entry.project_id)
        if not project:
            return False
        return project.tenant_id in principal.tenant_ids

    def _ensure_entry_access(self, entry: MemoryEntry, principal: AuthPrincipal | None) -> None:
        if not self._can_access_entry(entry, principal):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project access denied")

    @staticmethod
    def _build_search_payload(title: str | None, content: str) -> str:
        # Keep a normalized search payload in the row even when Postgres FTS is not available.
        return " ".join(part.strip() for part in [title or "", content] if part and part.strip())
